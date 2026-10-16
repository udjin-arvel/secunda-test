#!/usr/bin/env python3
"""Быстрый прогон сценариев API против запущенного стека (docker compose up)."""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from decimal import Decimal

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_API_KEY = "super-puper-secret-key"
WEBHOOK_URL = "https://example.com/webhook"


class ScenarioError(Exception):
    pass


def _client(base_url: str, api_key: str | None = None) -> httpx.Client:
    headers: dict[str, str] = {}
    if api_key is not None:
        headers["X-API-Key"] = api_key
    return httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=30.0)


def _payment_payload(**overrides) -> dict:
    body = {
        "amount": "10.00",
        "currency": "RUB",
        "description": "smoke test",
        "metadata": {"source": "smoke_test"},
        "webhook_url": WEBHOOK_URL,
    }
    body.update(overrides)
    return body


def run_scenario(name: str, fn) -> None:
    print(f"  - {name} ... ", end="", flush=True)
    try:
        fn()
    except ScenarioError as exc:
        print("FAIL")
        print(f"    {exc}")
        raise
    except httpx.HTTPError as exc:
        print("FAIL")
        print(f"    HTTP error: {exc}")
        raise ScenarioError(str(exc)) from exc
    print("OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", DEFAULT_BASE_URL),
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("API_KEY", DEFAULT_API_KEY),
        help="Valid X-API-Key",
    )
    parser.add_argument(
        "--skip-processing",
        action="store_true",
        help="Не ждать смены статуса pending -> succeeded/failed",
    )
    parser.add_argument(
        "--processing-timeout",
        type=float,
        default=90.0,
        help="Секунд ожидания обработки платежа (default: 90)",
    )
    args = parser.parse_args()

    base = args.base_url
    key = args.api_key
    idem = f"smoke-{uuid.uuid4()}"
    missing_id = "00000000-0000-0000-0000-000000000099"

    print(f"Smoke scenarios -> {base}\n")

    with _client(base) as anon, _client(base, key) as authed:
        run_scenario(
            "GET без API-ключа -> 401",
            lambda: _expect_status(
                anon.get(f"/api/v1/payments/{missing_id}"),
                401,
            ),
        )
        run_scenario(
            "GET с неверным API-ключом -> 401",
            lambda: _expect_status(
                anon.get(
                    f"/api/v1/payments/{missing_id}",
                    headers={"X-API-Key": "wrong-key"},
                ),
                401,
            ),
        )
        run_scenario(
            "POST без Idempotency-Key -> 400",
            lambda: _expect_status(
                authed.post("/api/v1/payments", json=_payment_payload()),
                400,
            ),
        )
        run_scenario(
            "POST с невалидным amount -> 422",
            lambda: _expect_status(
                authed.post(
                    "/api/v1/payments",
                    json=_payment_payload(amount="0"),
                    headers={"Idempotency-Key": f"{idem}-invalid"},
                ),
                422,
            ),
        )

        create_resp = None
        payment_id = None

        def create_payment() -> None:
            nonlocal create_resp, payment_id
            create_resp = authed.post(
                "/api/v1/payments",
                json=_payment_payload(amount="25.50"),
                headers={"Idempotency-Key": idem},
            )
            _expect_status(create_resp, 202)
            data = create_resp.json()
            if data.get("status") != "pending":
                raise ScenarioError(f"ожидался pending, получено {data.get('status')}")
            payment_id = data["payment_id"]

        run_scenario("POST создание платежа -> 202, pending", create_payment)

        def idempotent_replay() -> None:
            assert payment_id is not None
            resp = authed.post(
                "/api/v1/payments",
                json=_payment_payload(amount="25.50"),
                headers={"Idempotency-Key": idem},
            )
            _expect_status(resp, 200)
            data = resp.json()
            if data["payment_id"] != payment_id:
                raise ScenarioError("повторный запрос вернул другой payment_id")

        run_scenario("POST тот же Idempotency-Key -> 200, тот же payment_id", idempotent_replay)

        def get_payment() -> None:
            assert payment_id is not None
            resp = authed.get(f"/api/v1/payments/{payment_id}")
            _expect_status(resp, 200)
            data = resp.json()
            if data["id"] != payment_id:
                raise ScenarioError("id в ответе не совпадает")
            if Decimal(str(data["amount"])) != Decimal("25.50"):
                raise ScenarioError(f"amount={data['amount']}")
            if data["currency"] != "RUB":
                raise ScenarioError(f"currency={data['currency']}")

        run_scenario("GET существующий платёж -> 200", get_payment)

        run_scenario(
            "GET несуществующий платёж -> 404",
            lambda: _expect_status(
                authed.get(f"/api/v1/payments/{missing_id}"),
                404,
            ),
        )

        if not args.skip_processing:
            run_scenario(
                "Ожидание обработки consumer (succeeded или failed)",
                lambda: _wait_processed(
                    authed,
                    payment_id,
                    timeout=args.processing_timeout,
                ),
            )

    print("\nВсе сценарии прошли успешно.")
    return 0


def _expect_status(response: httpx.Response, expected: int) -> None:
    if response.status_code != expected:
        body = response.text[:500]
        raise ScenarioError(f"HTTP {response.status_code}, ожидался {expected}: {body}")


def _wait_processed(
    client: httpx.Client,
    payment_id: str | None,
    timeout: float,
    poll_interval: float = 2.0,
) -> None:
    if payment_id is None:
        raise ScenarioError("payment_id не задан")

    deadline = time.monotonic() + timeout
    last_status = "pending"
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/payments/{payment_id}")
        _expect_status(resp, 200)
        last_status = resp.json().get("status", "")
        if last_status in ("succeeded", "failed"):
            if resp.json().get("processed_at") is None:
                raise ScenarioError(f"status={last_status}, но processed_at пустой")
            return
        time.sleep(poll_interval)

    raise ScenarioError(
        f"таймаут {timeout}s, последний status={last_status} (проверьте consumer и outbox-publisher)"
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScenarioError:
        print("\nSmoke test завершился с ошибкой.", file=sys.stderr)
        raise SystemExit(1) from None
