from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import ActorType
from core.db.models import AuditLog


async def record_audit(
    db: AsyncSession,
    *,
    actor_type: ActorType,
    actor_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    meta: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            meta=meta or {},
        )
    )
