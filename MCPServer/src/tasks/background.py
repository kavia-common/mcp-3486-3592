from __future__ import annotations

import asyncio
import logging
import os
import signal
from contextlib import suppress
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..db.session import SessionLocal
from ..db.models import Message, MessageStatus, JiraSync, JiraSyncStatus
from ..services.jira_sync_service import ensure_issue_for_message, record_sync_status
from ..services.message_processor import process_message
from ..utils.rate_limit import TokenBucket
from ..utils.errors import is_transient_error

logger = logging.getLogger(__name__)


class BackgroundScheduler:
    """Simple asyncio-based background scheduler for periodic maintenance tasks.

    Starts a background loop that:
    - Processes pending messages (status='pending') using service rules.
    - Processes pending JiraSync records (sync_status='pending'), attempting ensure/create.

    Features:
    - Rate limiting for Jira operations via token bucket (env JIRA_RATE_LIMIT_PER_MIN, default 60/min).
    - Configurable loop interval via env BACKGROUND_LOOP_INTERVAL_SECONDS (default 5s).
    - Minimal retry/backoff on transient failures.
    - Graceful shutdown on application stop.
    """

    def __init__(self) -> None:
        # Loop tick interval
        self.interval_seconds: float = float(os.getenv("BACKGROUND_LOOP_INTERVAL_SECONDS", "5"))
        # Rate limiting for Jira calls
        per_min = int(os.getenv("JIRA_RATE_LIMIT_PER_MIN", "60"))
        self.jira_bucket = TokenBucket(rate_per_sec=max(1.0, per_min) / 60.0, capacity=max(1, per_min))
        # Control
        self._task: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()
        self._started = False
        self._loop = None  # store loop reference for shutdown logs
        logger.info(
            "BackgroundScheduler initialized: interval=%.2fs, jira_per_min=%s",
            self.interval_seconds,
            per_min,
        )

    async def start(self) -> None:
        """Start the scheduler loop if not already running."""
        if self._started:
            return
        self._started = True
        self._stopping.clear()
        self._loop = asyncio.get_running_loop()
        # Setup signal handlers for graceful shutdown if running in main loop context
        with suppress(NotImplementedError):
            for sig in (signal.SIGINT, signal.SIGTERM):
                self._loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.shutdown(reason=f"signal {s.name}")))
        self._task = asyncio.create_task(self._run_loop(), name="background-scheduler")
        logger.info("BackgroundScheduler started.")

    async def shutdown(self, reason: str = "shutdown") -> None:
        """Request graceful shutdown and wait for the loop to exit."""
        if not self._started:
            return
        logger.info("BackgroundScheduler stopping due to %s ...", reason)
        self._stopping.set()
        if self._task:
            # give the task a chance to finish current iteration
            try:
                await asyncio.wait_for(self._task, timeout=self.interval_seconds + 3.0)
            except asyncio.TimeoutError:
                logger.warning("BackgroundScheduler did not stop in time, cancelling task...")
                self._task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._task
        self._task = None
        self._started = False
        logger.info("BackgroundScheduler stopped.")

    async def _run_loop(self) -> None:
        """Main loop: periodically run workers and sleep for interval."""
        try:
            while not self._stopping.is_set():
                try:
                    await self._tick()
                except Exception as e:  # pragma: no cover - defensive
                    logger.exception("Background loop iteration error: %s", e)
                # Sleep with cancellation awareness
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self.interval_seconds)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:  # pragma: no cover - expected on shutdown
            logger.debug("Background loop cancelled.")
            raise

    async def _tick(self) -> None:
        """Single iteration: process messages and Jira syncs."""
        # Process pending messages (limited batch)
        await self._process_pending_messages(max_items=20)
        # Process Jira syncs with rate limiting
        await self._process_pending_jira_syncs(max_items=10)

    async def _process_pending_messages(self, max_items: int = 20) -> None:
        """Find pending messages and process each with retry on transient errors."""
        db: Session = SessionLocal()
        try:
            items = (
                db.query(Message)
                .filter(Message.status == MessageStatus.pending)
                .order_by(Message.created_at.asc())
                .limit(max_items)
                .all()
            )
            if not items:
                return

            logger.debug("Found %d pending messages to process.", len(items))
            for msg in items:
                # minimal retry with exponential backoff for transient problems
                max_attempts = 3
                for attempt in range(1, max_attempts + 1):
                    try:
                        ok = await process_message(db, msg)
                        # process_message is responsible to set db state for message
                        db.commit()
                        if ok:
                            logger.info("Processed message id=%s", msg.id)
                        else:
                            logger.warning("Processing returned false for message id=%s", msg.id)
                        break
                    except Exception as e:
                        db.rollback()
                        if attempt < max_attempts and is_transient_error(e):
                            delay = 0.5 * (2 ** (attempt - 1))
                            logger.warning(
                                "Transient error processing message=%s: %s; retrying in %.2fs (%d/%d)",
                                msg.id, repr(e), delay, attempt, max_attempts
                            )
                            await asyncio.sleep(delay)
                            continue
                        # Mark failed
                        logger.exception("Failed to process message=%s: %s", msg.id, e)
                        try:
                            msg.status = MessageStatus.failed
                            msg.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                            db.add(msg)
                            db.commit()
                        except Exception:  # pragma: no cover - defensive
                            db.rollback()
                        break
        finally:
            db.close()

    async def _process_pending_jira_syncs(self, max_items: int = 10) -> None:
        """Process JiraSync records in 'pending' state with rate-limited Jira calls."""
        # Respect token bucket; if no tokens, skip this tick
        # We will attempt to refill and consume per item
        db: Session = SessionLocal()
        try:
            items = (
                db.query(JiraSync)
                .filter(JiraSync.sync_status == JiraSyncStatus.pending)
                .order_by(JiraSync.last_synced_at.asc().nullsfirst())
                .limit(max_items)
                .all()
            )
            if not items:
                return

            logger.debug("Found %d pending JiraSync records.", len(items))

            for sync in items:
                # Check rate limit token before Jira operation
                if not self.jira_bucket.try_consume(1):
                    logger.info("Jira rate limit reached; deferring remaining syncs to later ticks.")
                    break

                # If linked to a message, ensure issue exists; else just mark as pending and move along
                message_id = sync.message_id
                jira_issue_id = sync.jira_issue_id

                # Retry on transient failures
                max_attempts = 3
                for attempt in range(1, max_attempts + 1):
                    try:
                        if message_id:
                            issue_key = await ensure_issue_for_message(db, message_id)
                            if issue_key:
                                record_sync_status(db, issue_key, message_id, JiraSyncStatus.synced, details="background ensure ok")
                            else:
                                record_sync_status(db, jira_issue_id or "unknown", message_id, JiraSyncStatus.error, details="background ensure failed")
                        else:
                            # No message, attempt to verify existence best-effort by reusing ensure path via None is not supported.
                            # We simply mark as pending (no-op) to be handled by external webhook or manual trigger.
                            record_sync_status(db, jira_issue_id, None, JiraSyncStatus.pending, details="no associated message - waiting")
                        db.commit()
                        break
                    except Exception as e:
                        db.rollback()
                        if attempt < max_attempts and is_transient_error(e):
                            delay = 0.5 * (2 ** (attempt - 1))
                            logger.warning(
                                "Transient error syncing jira_issue=%s message=%s: %s; retrying in %.2fs (%d/%d)",
                                jira_issue_id, message_id, repr(e), delay, attempt, max_attempts
                            )
                            await asyncio.sleep(delay)
                            continue
                        logger.exception(
                            "Failed to process JiraSync id=%s issue=%s message=%s: %s",
                            sync.id, jira_issue_id, message_id, e
                        )
                        try:
                            record_sync_status(db, jira_issue_id or "unknown", message_id, JiraSyncStatus.error, details="exception in background")
                            db.commit()
                        except Exception:  # pragma: no cover
                            db.rollback()
                        break
        finally:
            db.close()


_scheduler: Optional[BackgroundScheduler] = None


# PUBLIC_INTERFACE
async def startup_background_tasks() -> None:
    """Start the background scheduler; call this in FastAPI startup event."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    await _scheduler.start()


# PUBLIC_INTERFACE
async def shutdown_background_tasks() -> None:
    """Stop the background scheduler; call this in FastAPI shutdown event."""
    global _scheduler
    if _scheduler is not None:
        await _scheduler.shutdown("app shutdown")
        _scheduler = None
