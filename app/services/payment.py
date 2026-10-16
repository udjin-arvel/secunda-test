from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.schemas.payment import PaymentCreate
from app.services.outbox import enqueue_payment_created


async def get_by_idempotency_key(session: AsyncSession, key: str) -> Payment | None:
    result = await session.execute(select(Payment).where(Payment.idempotency_key == key))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, payment_id) -> Payment | None:
    result = await session.execute(select(Payment).where(Payment.id == payment_id))
    return result.scalar_one_or_none()


async def create_payment(
    session: AsyncSession, body: PaymentCreate, idempotency_key: str
) -> tuple[Payment, bool]:
    existing = await get_by_idempotency_key(session, idempotency_key)
    if existing is not None:
        return existing, False

    payment = Payment(
        amount=body.amount,
        currency=body.currency,
        description=body.description,
        metadata_=body.metadata,
        idempotency_key=idempotency_key,
        webhook_url=str(body.webhook_url),
    )
    session.add(payment)
    await session.flush()

    await enqueue_payment_created(session, payment.id)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raced = await get_by_idempotency_key(session, idempotency_key)
        if raced is None:
            raise
        return raced, False

    await session.refresh(payment)
    return payment, True
