import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import httpx

from app.constants import Currency, PaymentStatus
from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def send_payment_webhook(
    webhook_url: str,
    payment_id: UUID,
    status: PaymentStatus,
    amount: Decimal,
    currency: Currency,
    processed_at: datetime,
) -> None:
    settings = get_settings()
    payload = {
        "payment_id": str(payment_id),
        "status": status.value,
        "amount": str(amount),
        "currency": currency.value,
        "processed_at": processed_at.isoformat(),
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(settings.webhook_max_attempts):
            try:
                resp = await client.post(webhook_url, json=payload)
                if resp.is_success:
                    return
                logger.warning(
                    "Webhook non-success payment_id=%s status=%s attempt=%s",
                    payment_id,
                    resp.status_code,
                    attempt + 1,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "Webhook error payment_id=%s attempt=%s error=%s",
                    payment_id,
                    attempt + 1,
                    exc,
                )

            if attempt + 1 < settings.webhook_max_attempts:
                delay = settings.webhook_backoff_base * (2**attempt)
                await asyncio.sleep(delay)

    logger.error(
        "Webhook exhausted retries payment_id=%s url=%s",
        payment_id,
        webhook_url,
    )
