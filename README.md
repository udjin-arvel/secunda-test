# Asynchronous payment processing service

Асинхронный микросервис: приём платежей через API, outbox, RabbitMQ, обработка запроса с эмуляцией реального шлюза (90% успех, 10% провал - эмулируется в `handler.py`) и webhook с retry.

Стек: FastAPI, SQLAlchemy 2 async, PostgreSQL, RabbitMQ (фв FastStream), Alembic, Docker. 

Повторная доставка из outbox безопасна: consumer идемпотентен (по статусу pending).

## Запуск

```bash
docker compose up --build
```

API: http://localhost:8000  
RabbitMQ Management: http://localhost:15672 (вход guest / guest)

## Быстрый smoke-тест

После `docker compose up` можно прогнать все основные сценарии API (ключ, идемпотентность, валидация, 404) и дождаться обработки платежа в консьюмере:

```bash
uv run python scripts/smoke_test.py
```

Только HTTP без ожидания consumer:

```bash
uv run python scripts/smoke_test.py --skip-processing
```

Переменные окружения: `BASE_URL` (по умолчанию `http://localhost:8000`), `API_KEY` (как в `.env`). Доступные флаги: `--base-url`, `--api-key`, `--skip-processing`, `--processing-timeout`.

Через Makefile (нужны `make` и `uv`):

| Команда | Назначение |
|---------|------------|
| `make up` | Поднять стек в фоне |
| `make smoke` | Полный smoke-тест |
| `make smoke-fast` | Smoke без ожидания consumer |
| `make up-smoke` | `up` + ожидание API + `smoke` |
| `make down` | Остановить стек |
| `make consumer-logs` | Логи consumer |

## Примеры curl

Создание платежа:

```bash
curl -s -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: super-puper-secret-key" \
  -H "Idempotency-Key: order-123" \
  -d '{
    "amount": "100.50",
    "currency": "RUB",
    "description": "Order #123",
    "metadata": {"order_id": "123"},
    "webhook_url": "https://webhook.site/your-unique-id"
  }'
```

Повтор с тем же `Idempotency-Key` (200, тот же `payment_id`):

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: super-puper-secret-key" \
  -H "Idempotency-Key: order-123" \
  -d '{
    "amount": "100.50",
    "currency": "RUB",
    "webhook_url": "https://webhook.site/your-unique-id"
  }'
```

Получение платежа:

```bash
curl -s http://localhost:8000/api/v1/payments/<payment_id> \
  -H "X-API-Key: super-puper-secret-key"
```

Без API-ключа (401):

```bash
curl -s -w "\nHTTP %{http_code}\n" http://localhost:8000/api/v1/payments/00000000-0000-0000-0000-000000000001
```

## RabbitMQ

В браузере откройте **Queues**: `payments.new`, `payments.new.retry`, `payments.new.dlq`. После создания платежа в `payments.new` появляется сообщение, и консьюмер его подбирает.

## DLQ

Сообщения попадают в `payments.new.dlq` после трёх неудачных попыток обработки (с задержкой через retry-очередь). Логи consumer показывают `Message in DLQ: ...`. В RabbitMQ Management смотрите счётчик сообщений в `payments.new.dlq`.
