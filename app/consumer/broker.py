from faststream import FastStream
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.constants import (
    EXCHANGE_PAYMENTS,
    QUEUE_PAYMENTS_DLQ,
    QUEUE_PAYMENTS_NEW,
    QUEUE_PAYMENTS_RETRY,
    ROUTING_PAYMENTS_DLQ,
    ROUTING_PAYMENTS_NEW,
    ROUTING_PAYMENTS_RETRY,
)
from app.core.config import get_settings

settings = get_settings()
broker = RabbitBroker(settings.rabbitmq_url)

payments_exchange = RabbitExchange(
    EXCHANGE_PAYMENTS,
    type=ExchangeType.DIRECT,
    durable=True,
)

dlq_queue = RabbitQueue(
    QUEUE_PAYMENTS_DLQ,
    durable=True,
    routing_key=ROUTING_PAYMENTS_DLQ,
)

retry_queue = RabbitQueue(
    QUEUE_PAYMENTS_RETRY,
    durable=True,
    routing_key=ROUTING_PAYMENTS_RETRY,
    arguments={
        "x-dead-letter-exchange": EXCHANGE_PAYMENTS,
        "x-dead-letter-routing-key": ROUTING_PAYMENTS_NEW,
    },
)

payments_new_queue = RabbitQueue(
    QUEUE_PAYMENTS_NEW,
    durable=True,
    routing_key=ROUTING_PAYMENTS_NEW,
    arguments={
        "x-dead-letter-exchange": EXCHANGE_PAYMENTS,
        "x-dead-letter-routing-key": ROUTING_PAYMENTS_DLQ,
    },
)
