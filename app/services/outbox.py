from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import OutboxEventType, OutboxStatus
from app.models.outbox import Outbox


async def enqueue_payment_created(session: AsyncSession, payment_id: UUID) -> Outbox:
    row = Outbox(
        event_type=OutboxEventType.PAYMENT_CREATED.value,
        payload={"payment_id": str(payment_id)},
        status=OutboxStatus.PENDING,
    )
    session.add(row)
    return row
