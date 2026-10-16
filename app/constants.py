from enum import StrEnum


class Currency(StrEnum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class OutboxEventType(StrEnum):
    PAYMENT_CREATED = "payment.created"


EXCHANGE_PAYMENTS = "payments"
QUEUE_PAYMENTS_NEW = "payments.new"
QUEUE_PAYMENTS_RETRY = "payments.new.retry"
QUEUE_PAYMENTS_DLQ = "payments.new.dlq"
ROUTING_PAYMENTS_NEW = "payments.new"
ROUTING_PAYMENTS_RETRY = "payments.new.retry"
ROUTING_PAYMENTS_DLQ = "payments.new.dlq"

HEADER_RETRY_COUNT = "x-retry-count"
MAX_MESSAGE_RETRIES = 3
RETRY_DELAY_MS = 5000
