import asyncio
import logging
from datetime import datetime, timezone

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from sqlalchemy import select

from app.constants import EXCHANGE_PAYMENTS, OutboxStatus, ROUTING_PAYMENTS_NEW
from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.outbox import Outbox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


payments_exchange = RabbitExchange(
    EXCHANGE_PAYMENTS,
    type=ExchangeType.DIRECT,
    durable=True,
)


async def publish_pending(broker: RabbitBroker) -> int:
    settings = get_settings()
    published = 0

    async with async_session_factory() as session:
        stmt = (
            select(Outbox)
            .where(Outbox.status == OutboxStatus.PENDING)
            .order_by(Outbox.created_at)
            .limit(settings.outbox_batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        rows = list(result.scalars().all())

        for row in rows:
            try:
                await broker.publish(
                    row.payload,
                    exchange=payments_exchange,
                    routing_key=ROUTING_PAYMENTS_NEW,
                )
                row.status = OutboxStatus.PUBLISHED
                row.published_at = datetime.now(timezone.utc)
                published += 1
            except Exception as exc:
                row.attempts += 1
                row.last_error = str(exc)
                logger.warning(
                    "Outbox publish failed id=%s attempts=%s error=%s",
                    row.id,
                    row.attempts,
                    exc,
                )
                if row.attempts >= settings.outbox_max_attempts:
                    row.status = OutboxStatus.FAILED

        await session.commit()

    return published


async def run_loop() -> None:
    settings = get_settings()
    broker = RabbitBroker(settings.rabbitmq_url)
    await broker.start()

    logger.info("Outbox publisher started")
    try:
        while True:
            count = await publish_pending(broker)
            if count:
                logger.info("Published %s outbox messages", count)
            await asyncio.sleep(settings.outbox_poll_interval)
    finally:
        await broker.stop()


def main() -> None:
    asyncio.run(run_loop())


if __name__ == "__main__":
    main()
