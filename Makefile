.PHONY: up down build logs smoke smoke-fast ps api-logs consumer-logs outbox-logs

COMPOSE := docker compose
UV := uv
PYTHON := $(UV) run python

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

api-logs:
	$(COMPOSE) logs -f api

consumer-logs:
	$(COMPOSE) logs -f consumer

outbox-logs:
	$(COMPOSE) logs -f outbox-publisher

# Полный smoke: API + ожидание обработки в consumer (до ~90 с)
smoke:
	$(PYTHON) scripts/smoke_test.py

# Только HTTP-сценарии, без ожидания consumer
smoke-fast:
	$(PYTHON) scripts/smoke_test.py --skip-processing

# Поднять контейнеры и прогнать smoke (удобно, если вообще с нуля стартовать)
up-smoke: up
	@echo "Ждём готовности API..."
	@$(PYTHON) -c "import time, httpx; \
url='http://localhost:8000/openapi.json'; \
deadline=time.monotonic()+120; \
while time.monotonic()<deadline: \
  try: \
    r=httpx.get(url, timeout=2); \
    if r.status_code==200: break; \
  except httpx.HTTPError: pass; \
  time.sleep(2); \
else: raise SystemExit('API не ответил за 120 с')"
	$(MAKE) smoke
