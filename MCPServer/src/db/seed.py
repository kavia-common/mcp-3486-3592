from __future__ import annotations

import logging
import os
from typing import Optional

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.security import hash_password
from .session import SessionLocal
from .models import Base, User, Rule, Message, MessageStatus
from ..db.session import engine

logger = logging.getLogger(__name__)


def _env_flag_true(value: Optional[str]) -> bool:
    """Interpret env flags like 'true', '1', 'yes' as True."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


# PUBLIC_INTERFACE
def run_seed_if_enabled() -> None:
    """Run seed data creation if SEED_ON_START is true.

    This function is safe to call repeatedly (idempotent). It will:
    - Ensure database tables exist (only in development) before seeding.
    - Create an admin user using ADMIN_USERNAME/ADMIN_PASSWORD if not present.
    - Optionally insert one active Rule and a sample pending Message if none exist.

    Env flags/config:
    - SEED_ON_START=true|false (default false)
    - ADMIN_USERNAME (default 'admin')
    - ADMIN_PASSWORD (default 'admin123')
    - SEED_SAMPLE_RULE=true|false (default true)
    - SEED_SAMPLE_MESSAGE=true|false (default true)
    """
    if not _env_flag_true(os.getenv("SEED_ON_START")):
        return

    settings = get_settings()
    # In development, ensure tables exist before seeding
    if settings.ENV.lower() == "development":
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("Failed to create tables before seeding: %s", e)

    db: Session = SessionLocal()
    try:
        _seed_admin_user(db)
        if _env_flag_true(os.getenv("SEED_SAMPLE_RULE", "true")):
            _seed_sample_rule(db)
        if _env_flag_true(os.getenv("SEED_SAMPLE_MESSAGE", "true")):
            _seed_sample_message(db)
        db.commit()
        logger.info("Database seeding completed (idempotent).")
    except Exception as e:  # pragma: no cover - defensive
        db.rollback()
        logger.exception("Seed operation failed: %s", e)
    finally:
        db.close()


def _seed_admin_user(db: Session) -> None:
    """Ensure an admin user exists using ADMIN_USERNAME/ADMIN_PASSWORD."""
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")

    existing: Optional[User] = db.query(User).filter(User.username == username).first()
    if existing:
        # Do not modify existing password/role here to keep idempotent and non-destructive
        logger.info("Admin user '%s' already exists; skipping creation.", username)
        return

    user = User(username=username, password_hash=hash_password(password), role="admin")
    db.add(user)
    logger.info("Created admin user '%s'.", username)


def _seed_sample_rule(db: Session) -> None:
    """Insert a single active Rule if none exist."""
    any_rule = db.query(Rule).first()
    if any_rule:
        logger.info("At least one rule already exists; skipping sample rule.")
        return

    rule = Rule(
        name="Prefix Rule",
        definition="prefix: [MCP]",
        is_active=True,
    )
    db.add(rule)
    logger.info("Inserted sample active Rule '%s'.", rule.name)


def _seed_sample_message(db: Session) -> None:
    """Insert a sample pending Message if none exist."""
    any_msg = db.query(Message).first()
    if any_msg:
        logger.info("At least one message already exists; skipping sample message.")
        return

    msg = Message(
        content="Hello from MCP sample message.",
        status=MessageStatus.pending,
        jira_issue_id=None,
    )
    db.add(msg)
    logger.info("Inserted sample pending Message '%s'.", msg.content[:40])
