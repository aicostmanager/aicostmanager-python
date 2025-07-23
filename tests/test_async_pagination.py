import asyncio

from aicostmanager.client import AsyncCostManagerClient
from aicostmanager.models import CustomerOut, PaginatedResponse, UsageEvent, UsageRollup


class DummyResponse:
    def __init__(self, data):
        self.status_code = 200
        self._data = data
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return self._data


def test_iter_usage_events(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk")
    client = AsyncCostManagerClient()

    pages = [
        {
            "results": [
                {
                    "event_id": "e1",
                    "config_id": "c",
                    "timestamp": "t",
                    "response_id": "r",
                    "status": "done",
                }
            ],
            "next": client.api_root + "/usage/events/?offset=1",
        },
        {
            "results": [
                {
                    "event_id": "e2",
                    "config_id": "c",
                    "timestamp": "t",
                    "response_id": "r",
                    "status": "done",
                }
            ],
            "next": None,
        },
    ]

    async def requester(self, method, url, **kwargs):
        return DummyResponse(pages.pop(0))

    monkeypatch.setattr("httpx.AsyncClient.request", requester)

    async def run():
        events = [e async for e in client.iter_usage_events()]
        assert [e.event_id for e in events] == ["e1", "e2"]

    asyncio.run(run())


def test_list_usage_events_typed(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk")
    client = AsyncCostManagerClient()

    data = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "event_id": "e1",
                "config_id": "c",
                "timestamp": "t",
                "response_id": "r",
                "status": "done",
            }
        ],
    }

    async def requester(self, method, url, **kwargs):
        return DummyResponse(data)

    monkeypatch.setattr("httpx.AsyncClient.request", requester)

    async def run():
        resp = await client.list_usage_events_typed()
        assert isinstance(resp, PaginatedResponse)
        assert isinstance(resp.results[0], UsageEvent)

    asyncio.run(run())


def test_list_usage_rollups_typed(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk")
    client = AsyncCostManagerClient()

    data = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "client_customer_key": "c1",
                "service_id": "svc",
                "date": "2024-01-01",
                "quantity": 1,
                "cost": 0.1,
            }
        ],
    }

    async def requester(self, method, url, **kwargs):
        return DummyResponse(data)

    monkeypatch.setattr("httpx.AsyncClient.request", requester)

    async def run():
        resp = await client.list_usage_rollups_typed()
        assert isinstance(resp, PaginatedResponse)
        assert isinstance(resp.results[0], UsageRollup)

    asyncio.run(run())


def test_list_customers_typed(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk")
    client = AsyncCostManagerClient()

    data = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "uuid": "u1",
                "client_customer_key": "c1",
                "name": "n",
                "phone": None,
                "email": None,
            }
        ],
    }

    async def requester(self, method, url, **kwargs):
        return DummyResponse(data)

    monkeypatch.setattr("httpx.AsyncClient.request", requester)

    async def run():
        resp = await client.list_customers_typed()
        assert isinstance(resp, PaginatedResponse)
        assert isinstance(resp.results[0], CustomerOut)

    asyncio.run(run())
