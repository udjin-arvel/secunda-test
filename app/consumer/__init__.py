from app.consumer import handler as handler  # noqa: F401
from app.consumer.broker import broker
from faststream import FastStream

app = FastStream(broker)
