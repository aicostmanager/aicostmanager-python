import asyncio

import pytest

from aicostmanager.client import AsyncCostManagerClient, CostManagerClient
from aicostmanager.config_manager import Config, CostManagerConfig
from aicostmanager import AsyncRestUsageWrapper, RestUsageWrapper


class DummyResponse:
    def __init__(self, data=None):
        self.status_code = 200
        self.headers = {"Content-Type": "application/json"}
        self._data = data or {"value": 5}

    def json(self):
        return self._data

    @property
    def text(self):
        import json

        return json.dumps(self._data)


class DummySession:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return DummyResponse()

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def patch(self, url, **kwargs):
        return self.request("PATCH", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def head(self, url, **kwargs):
        return self.request("HEAD", url, **kwargs)

    def options(self, url, **kwargs):
        return self.request("OPTIONS", url, **kwargs)

    def close(self):
        pass


class DummyAsyncSession:
    def __init__(self):
        self.calls = []

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))

        class R:
            status_code = 200
            headers = {"Content-Type": "application/json"}

            def json(self):
                return {"value": 5}

            text = "{}"

        return R()

    async def get(self, url, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def put(self, url, **kwargs):
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url, **kwargs):
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url, **kwargs):
        return await self.request("DELETE", url, **kwargs)

    async def head(self, url, **kwargs):
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url, **kwargs):
        return await self.request("OPTIONS", url, **kwargs)

    async def aclose(self):
        pass


@pytest.fixture(autouse=True)
def set_key(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    yield


@pytest.fixture
def config(monkeypatch):
    cfg = Config(
        uuid="cfg-1",
        config_id="api.example.com",
        api_id="api.example.com",
        last_updated="2025-01-01T00:00:00Z",
        handling_config={
            "tracked_methods": ["GET /foo"],
            "response_fields": [{"key": "value", "path": "value"}],
            "payload_mapping": {
                "config": "config_identifier",
                "timestamp": "timestamp",
                "usage": "response_data.value",
            },
        },
    )
    monkeypatch.setattr(CostManagerConfig, "get_config", lambda self, api_id: [cfg])


class DummyClientInit:
    def __init__(
        self,
        *,
        aicm_api_key=None,
        aicm_api_base=None,
        aicm_api_url=None,
        aicm_ini_path=None,
        session=None,
        proxies=None,
        headers=None,
    ):
        self.api_key = aicm_api_key
        self.api_base = "http://x"
        self.api_url = "/api"
        self.session = session or DummySession()
        # Use provided path or a safe default that won't create files in project root
        self.ini_path = aicm_ini_path or "/tmp/test_ini"


class DummyAsyncClientInit:
    def __init__(
        self,
        *,
        aicm_api_key=None,
        aicm_api_base=None,
        aicm_api_url=None,
        aicm_ini_path=None,
        session=None,
        proxies=None,
        headers=None,
    ):
        self.api_key = aicm_api_key
        self.api_base = "http://x"
        self.api_url = "/api"
        self.session = session or DummyAsyncSession()
        # Use provided path or a safe default that won't create files in project root
        self.ini_path = aicm_ini_path or "/tmp/test_ini"


def test_rest_manager_tracks(monkeypatch, config):
    monkeypatch.setattr(CostManagerClient, "__init__", DummyClientInit.__init__)
    session = DummySession()
    manager = RestUsageWrapper(session, base_url="https://api.example.com")
    resp = manager.get("/foo")
    assert resp.json() == {"value": 5}
    payloads = manager.get_tracked_payloads()
    assert len(payloads) == 1
    assert payloads[0]["usage"] == 5


def test_async_rest_manager_tracks(monkeypatch, config):
    monkeypatch.setattr(
        AsyncCostManagerClient, "__init__", DummyAsyncClientInit.__init__
    )
    monkeypatch.setattr(CostManagerClient, "__init__", DummyClientInit.__init__)

    async def run():
        session = DummyAsyncSession()
        manager = AsyncRestUsageWrapper(session, base_url="https://api.example.com")
        resp = await manager.get("/foo")
        assert resp.json() == {"value": 5}
        payloads = manager.get_tracked_payloads()
        assert len(payloads) == 1
        assert payloads[0]["usage"] == 5
        await manager.stop_delivery()

    asyncio.run(run())


def test_rest_client_customer_key_and_context(monkeypatch, config):
    monkeypatch.setattr(CostManagerClient, "__init__", DummyClientInit.__init__)
    session = DummySession()
    manager = RestUsageWrapper(
        session,
        base_url="https://api.example.com",
        client_customer_key="c1",
        context={"foo": "bar"},
    )
    manager.get("/foo")
    manager.set_client_customer_key("c2")
    manager.set_context({"baz": "qux"})
    manager.get("/foo")
    payloads = manager.get_tracked_payloads()
    assert payloads[0]["client_customer_key"] == "c1"
    assert payloads[0]["context"] == {"foo": "bar"}
    assert payloads[1]["client_customer_key"] == "c2"
    assert payloads[1]["context"] == {"baz": "qux"}


def test_async_rest_client_customer_key_and_context(monkeypatch, config):
    monkeypatch.setattr(
        AsyncCostManagerClient, "__init__", DummyAsyncClientInit.__init__
    )
    monkeypatch.setattr(CostManagerClient, "__init__", DummyClientInit.__init__)

    async def run():
        session = DummyAsyncSession()
        manager = AsyncRestUsageWrapper(
            session,
            base_url="https://api.example.com",
            client_customer_key="c1",
            context={"foo": "bar"},
        )
        await manager.get("/foo")
        manager.set_client_customer_key("c2")
        manager.set_context({"baz": "qux"})
        await manager.get("/foo")
        payloads = manager.get_tracked_payloads()
        assert payloads[0]["client_customer_key"] == "c1"
        assert payloads[0]["context"] == {"foo": "bar"}
        assert payloads[1]["client_customer_key"] == "c2"
        assert payloads[1]["context"] == {"baz": "qux"}
        await manager.stop_delivery()

    asyncio.run(run())
