import asyncio
import logging
import random
from datetime import datetime, timezone
from uuid import UUID

from faststream.exceptions import RejectMessage
from faststream.rabbit import RabbitMessage

from app.constants import (
    HEADER_RETRY_COUNT,
    MAX_MESSAGE_RETRIES,
    PaymentStatus,
    RETRY_DELAY_MS,
    ROUTING_PAYMENTS_RETRY,
)
from app.consumer.broker import (
    broker,
    dlq_queue,
    payments_exchange,
    payments_new_queue,
)
from app.consumer.webhook import send_payment_webhook
from app.db.session import async_session_factory
from app.services.payment import get_by_id

logger = logging.getLogger(__name__)


@broker.subscriber(dlq_queue, exchange=payments_exchange)
async def handle_dlq(body: dict) -> None:
    logger.error("Message in DLQ: %s", body)


@broker.subscriber(payments_new_queue, exchange=payments_exchange)
async def handle_payment_new(body: dict, msg: RabbitMessage) -> None:
    try:
        await _process_payment(body)
    except RejectMessage:
        raise
    except Exception:
        logger.exception("Payment handler failed body=%s", body)
        await _handle_retry(body, msg)


async def _process_payment(body: dict) -> None:
    raw_id = body.get("payment_id")
    if not raw_id:
        logger.warning("Message without payment_id: %s", body)
        return

    try:
        payment_id = UUID(str(raw_id))
    except ValueError:
        logger.error("Invalid payment_id: %s", raw_id)
        raise RejectMessage("Invalid payment_id")

    async with async_session_factory() as session:
        payment = await get_by_id(session, payment_id)
        if payment is None:
            logger.warning("Payment not found payment_id=%s", payment_id)
            return
        if payment.status != PaymentStatus.PENDING:
            logger.info(
                "Payment already processed payment_id=%s status=%s",
                payment_id,
                payment.status,
            )
            return

        await asyncio.sleep(random.uniform(2, 5))

        # Эмуляция случайного статуса 90% успешного, 10% неуспешного
        new_status = (
            PaymentStatus.SUCCEEDED if random.random() < 0.9 else PaymentStatus.FAILED
        )
        processed_at = datetime.now(timezone.utc)
        payment.status = new_status
        payment.processed_at = processed_at
        await session.commit()

        webhook_url = payment.webhook_url
        amount = payment.amount
        currency = payment.currency

    # Статус уже в БД; сбой webhook не откатываем.
    await send_payment_webhook(
        webhook_url,
        payment_id,
        new_status,
        amount,
        currency,
        processed_at,
    )


async def _handle_retry(body: dict, msg: RabbitMessage) -> None:
    headers = dict(msg.headers or {})
    raw_count = headers.get(HEADER_RETRY_COUNT, 0)
    count = int(raw_count) if raw_count is not None else 0

    if count + 1 >= MAX_MESSAGE_RETRIES:
        raise RejectMessage()

    await broker.publish(
        body,
        exchange=payments_exchange,
        routing_key=ROUTING_PAYMENTS_RETRY,
        headers={HEADER_RETRY_COUNT: count + 1},
        expiration=RETRY_DELAY_MS,
    )
