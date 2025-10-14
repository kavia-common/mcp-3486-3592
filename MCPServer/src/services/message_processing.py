from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# PUBLIC_INTERFACE
def enqueue_message_processing(message_id: str) -> None:
    """
    Stub for message processing enqueue.

    In production, this could push a job to a queue (e.g., Celery, RQ, or a custom worker).
    For now, we log the intent and return immediately.

    Parameters:
    - message_id: The ID of the message to process (as string to simplify background task serialization).
    """
    # Here we only log; the actual processor could be implemented later.
    logger.info("Enqueued processing for message_id=%s", message_id)
