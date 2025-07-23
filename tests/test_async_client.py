import asyncio
import json
from typing import Any

import pytest

from aicostmanager.client import APIRequestError, AsyncCostManagerClient
from aicostmanager.models import (
    ApiUsageRecord,
    ApiUsageRequest,
    CustomerFilters,
    CustomerIn,
    Period,
    RollupFilters,
    ThresholdType,
    UsageEventFilters,
    UsageLimitIn,
)


class DummyResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._content = json.dumps(data or {}).encode()
        self.headers = {"Content-Type": "application/json"}
        self.text = self._content.decode()

    def json(self):
        return json.loads(self._content)


def _patch(monkeypatch, method, path, data=None, status=200):
    async def requester(self, m, url, **kwargs):
        assert m == method
        assert url.endswith(path)
        assert self.headers["Authorization"].startswith("Bearer ")
        return DummyResponse(status_code=status, data=data)

    monkeypatch.setattr("httpx.AsyncClient.request", requester)


def test_async_methods(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    client = AsyncCostManagerClient()

    record = ApiUsageRecord(
        config_id="cfg", service_id="svc", timestamp="t", response_id="r", usage={}
    )
    specs = [
        (
            "GET",
            "/configs",
            client.get_configs,
            (),
            {},
            {"service_configs": [], "triggered_limits": {}},
        ),
        (
            "POST",
            "/track-usage",
            client.track_usage,
            (ApiUsageRequest(usage_records=[record]),),
            {},
            {"event_ids": [], "triggered_limits": {}},
            201,
        ),
        (
            "GET",
            "/usage/events/",
            client.list_usage_events,
            (),
            {"limit": 1},
            {"count": 0, "next": None, "previous": None, "results": []},
        ),
        (
            "GET",
            "/usage/event/evt/",
            client.get_usage_event,
            ("evt",),
            {},
            {
                "event_id": "evt",
                "config_id": "cfg",
                "timestamp": "t",
                "response_id": "r",
                "status": "done",
            },
        ),
        (
            "GET",
            "/usage/rollups/",
            client.list_usage_rollups,
            (),
            {},
            {"count": 0, "next": None, "previous": None, "results": []},
        ),
        (
            "GET",
            "/customers/",
            client.list_customers,
            (),
            {},
            {"count": 0, "next": None, "previous": None, "results": []},
        ),
        (
            "POST",
            "/customers/",
            client.create_customer,
            (CustomerIn(client_customer_key="c"),),
            {},
            {
                "uuid": "c1",
                "client_customer_key": "c",
                "name": None,
                "phone": None,
                "email": None,
            },
            201,
        ),
        (
            "GET",
            "/customers/cid/",
            client.get_customer,
            ("cid",),
            {},
            {
                "uuid": "cid",
                "client_customer_key": "c",
                "name": None,
                "phone": None,
                "email": None,
            },
        ),
        (
            "PUT",
            "/customers/cid/",
            client.update_customer,
            ("cid", CustomerIn(client_customer_key="c", name="y")),
            {},
            {
                "uuid": "cid",
                "client_customer_key": "c",
                "name": "y",
                "phone": None,
                "email": None,
            },
        ),
        ("DELETE", "/customers/cid/", client.delete_customer, ("cid",), {}, None, 204),
        ("GET", "/usage-limits/", client.list_usage_limits, (), {}, []),
        (
            "POST",
            "/usage-limits/",
            client.create_usage_limit,
            (
                UsageLimitIn(
                    threshold_type=ThresholdType.LIMIT, amount=1, period=Period.DAY
                ),
            ),
            {},
            {
                "uuid": "lim",
                "threshold_type": "limit",
                "amount": 1,
                "period": "day",
                "vendor": None,
                "service": None,
                "client": None,
                "notification_list": None,
                "active": True,
            },
            201,
        ),
        (
            "GET",
            "/usage-limits/lid/",
            client.get_usage_limit,
            ("lid",),
            {},
            {
                "uuid": "lid",
                "threshold_type": "limit",
                "amount": 1,
                "period": "day",
                "vendor": None,
                "service": None,
                "client": None,
                "notification_list": None,
                "active": True,
            },
        ),
        (
            "PUT",
            "/usage-limits/lid/",
            client.update_usage_limit,
            (
                "lid",
                UsageLimitIn(
                    threshold_type=ThresholdType.ALERT, amount=2, period=Period.MONTH
                ),
            ),
            {},
            {
                "uuid": "lid",
                "threshold_type": "alert",
                "amount": 2,
                "period": "month",
                "vendor": None,
                "service": None,
                "client": None,
                "notification_list": None,
                "active": True,
            },
        ),
        (
            "DELETE",
            "/usage-limits/lid/",
            client.delete_usage_limit,
            ("lid",),
            {},
            None,
            204,
        ),
        (
            "GET",
            "/openapi.json",
            client.get_openapi_schema,
            (),
            {},
            {"openapi": "3.1.0"},
        ),
    ]

    async def run():
        for spec in specs:
            method, path, func, args, kwargs, data, *rest = spec
            status = rest[0] if rest else 200
            _patch(monkeypatch, method, client.api_root + path, data, status)
            result = await func(*args, **kwargs)
            from pydantic import BaseModel

            if data is None:
                assert result is None
            elif isinstance(result, BaseModel):
                assert isinstance(result, BaseModel)
            elif isinstance(data, list):
                assert isinstance(result, list)
            else:
                assert isinstance(result, dict)

    asyncio.run(run())


def test_async_filter_objects(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    client = AsyncCostManagerClient()

    captured: dict[str, Any] = {}

    async def requester(self, method, url, **kwargs):
        captured.update(kwargs)
        return DummyResponse(data={})

    monkeypatch.setattr("httpx.AsyncClient.request", requester)

    filters = UsageEventFilters(client_customer_key="c1")

    async def run():
        await client.list_usage_events(filters)

    asyncio.run(run())
    assert captured.get("params") == {"client_customer_key": "c1"}

    filters = RollupFilters(limit=10, offset=1)

    async def run2():
        await client.list_usage_rollups(filters)

    asyncio.run(run2())
    assert captured.get("params") == {"limit": 10, "offset": 1, "granularity": "daily"}

    filters = CustomerFilters(phone="p", limit=3)

    async def run3():
        await client.list_customers(filters)

    asyncio.run(run3())
    assert captured.get("params") == {"phone": "p", "limit": 3}


def test_async_error_response(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")

    async def requester(self, method, url, **kwargs):
        return DummyResponse(
            status_code=400,
            data={"error": "bad", "message": "oops", "timestamp": "now"},
        )

    monkeypatch.setattr("httpx.AsyncClient.request", requester)
    client = AsyncCostManagerClient()

    async def run():
        with pytest.raises(APIRequestError) as exc:
            await client.get_configs()
        err = exc.value
        assert err.error == "bad"
        assert err.message == "oops"

    asyncio.run(run())
