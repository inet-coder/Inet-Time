from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import AutomationStatus, ProfileField
from core.db.models import Automation, AutomationAction


async def find_conflicts(
    db: AsyncSession,
    telegram_account_id: int,
    fields: set[ProfileField],
    exclude_automation_id: int | None = None,
) -> list[dict]:
    """Berilgan fieldlarga hozir ACTIVE bo'lgan boshqa automationlar egalik qilyaptimi — field ownership tekshiruvi."""
    query = (
        select(Automation.id, Automation.priority, AutomationAction.field)
        .join(AutomationAction, AutomationAction.automation_id == Automation.id)
        .where(
            Automation.telegram_account_id == telegram_account_id,
            Automation.status == AutomationStatus.ACTIVE,
            AutomationAction.field.in_(fields),
        )
    )
    if exclude_automation_id is not None:
        query = query.where(Automation.id != exclude_automation_id)
    rows = (await db.execute(query)).all()
    return [{"automation_id": aid, "priority": priority.value, "field": field.value} for aid, priority, field in rows]
