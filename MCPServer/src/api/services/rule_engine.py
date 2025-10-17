from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import Message, Rule


class RuleEngine:
    """Simple rule engine placeholder that marks messages processed when active rules exist."""

    # PUBLIC_INTERFACE
    async def apply_rules(self, db: AsyncSession, message: Message) -> None:
        """Apply active rules to a message (MVP stub)."""
        # Fetch active rules to demonstrate DB interaction
        _ = await db.execute(Rule.__table__.select().where(Rule.is_active.is_(True)))
        # For MVP, no transformation; assume processing succeeds
        return
