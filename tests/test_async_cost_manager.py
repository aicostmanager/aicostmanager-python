import asyncio

import pytest

from aicostmanager import AsyncClientCostManager
from aicostmanager.client import AsyncCostManagerClient, CostManagerClient
from aicostmanager.config_manager import Config, CostManagerConfig


class DummyClient:
    async def add(self, *, a, b):
        return a + b


@pytest.fixture(autouse=True)
def set_key(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    yield


def test_async_manager_tracks(monkeypatch):
    cfg = Config(
        uuid="cfg-1",
        config_id="dummy",
        api_id="dummyclient",
        last_updated="2025-01-01T00:00:00Z",
        handling_config={
            "tracked_methods": ["add"],
            "request_fields": ["a", "b"],
            "response_fields": [{"key": "value", "path": ""}],
            "payload_mapping": {
                "config": "config_identifier",
                "timestamp": "timestamp",
                "usage": "response_data.value",
            },
            "static_payload_fields": {"static": 1},
        },
    )
    monkeypatch.setattr(CostManagerConfig, "get_config", lambda self, api_id: [cfg])

    def fake_async_init(
        self,
        *,
        aicm_api_key=None,
        aicm_api_base=None,
        aicm_api_url=None,
        aicm_ini_path=None,
        session=None,
    ):
        self.api_key = aicm_api_key
        self.api_base = "http://x"
        self.api_url = "/api"
        self.session = session or DummySession()
        # Use provided path or a safe default that won't create files in project root
        self.ini_path = aicm_ini_path or "/tmp/test_async_ini"

    def fake_sync_init(
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
        self.ini_path = aicm_ini_path or "/tmp/test_sync_ini"

    monkeypatch.setattr(AsyncCostManagerClient, "__init__", fake_async_init)
    monkeypatch.setattr(CostManagerClient, "__init__", fake_sync_init)

    async def run():
        manager = AsyncClientCostManager(DummyClient())
        result = await manager.add(a=2, b=3)
        assert result == 5
        payloads = manager.get_tracked_payloads()
        assert len(payloads) == 1
        assert payloads[0]["config"] == "dummy"
        assert payloads[0]["usage"] == 5
        await manager.stop_delivery()

    asyncio.run(run())


class DummySession:
    def __init__(self):
        self.calls = []

    async def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))

        class R:
            status_code = 200

            def raise_for_status(self):
                pass

        return R()

    def close(self):
        pass


def test_async_delivery(monkeypatch):
    session = DummySession()

    def fake_async_init(
        self,
        *,
        aicm_api_key=None,
        aicm_api_base=None,
        aicm_api_url=None,
        aicm_ini_path=None,
        session=None,
    ):
        self.api_key = aicm_api_key
        self.api_base = "http://x"
        self.api_url = "/api"
        self.session = session or session_obj
        # Use provided path or a safe default that won't create files in project root
        self.ini_path = aicm_ini_path or "/tmp/test_async_delivery_ini"

    def fake_sync_init(
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
        self.session = session or session_obj
        # Use provided path or a safe default that won't create files in project root
        self.ini_path = aicm_ini_path or "/tmp/test_sync_delivery_ini"

    session_obj = session
    monkeypatch.setattr(AsyncCostManagerClient, "__init__", fake_async_init)
    monkeypatch.setattr(CostManagerClient, "__init__", fake_sync_init)

    cfg = Config(
        uuid="cfg-1",
        config_id="dummy",
        api_id="dummyclient",
        last_updated="2025-01-01T00:00:00Z",
        handling_config={
            "tracked_methods": ["add"],
            "request_fields": ["a", "b"],
            "response_fields": [{"key": "value", "path": ""}],
            "payload_mapping": {
                "config": "config_identifier",
                "timestamp": "timestamp",
                "usage": "response_data.value",
            },
        },
    )
    monkeypatch.setattr(CostManagerConfig, "get_config", lambda self, api_id: [cfg])

    async def run():
        manager = AsyncClientCostManager(DummyClient(), delivery_queue_size=10)
        await asyncio.sleep(0)
        await manager.add(a=2, b=3)
        await manager.delivery._queue.join()
        await manager.stop_delivery()
        assert len(session.calls) == 1
        assert session.calls[0][1]["usage_records"][0]["usage"] == 5

    asyncio.run(run())


def test_async_client_customer_key_and_context(monkeypatch):
    cfg = Config(
        uuid="cfg-1",
        config_id="dummy",
        api_id="dummyclient",
        last_updated="2025-01-01T00:00:00Z",
        handling_config={
            "tracked_methods": ["add"],
            "request_fields": ["a", "b"],
            "response_fields": [{"key": "value", "path": ""}],
            "payload_mapping": {
                "config": "config_identifier",
                "timestamp": "timestamp",
                "usage": "response_data.value",
            },
        },
    )
    monkeypatch.setattr(CostManagerConfig, "get_config", lambda self, api_id: [cfg])

    def fake_async_init(self, *, aicm_api_key=None, aicm_api_base=None, aicm_api_url=None, aicm_ini_path=None, session=None):
        self.api_key = aicm_api_key
        self.api_base = "http://x"
        self.api_url = "/api"
        self.session = session or DummySession()
        self.ini_path = "ini"

    def fake_sync_init(self, *, aicm_api_key=None, aicm_api_base=None, aicm_api_url=None, aicm_ini_path=None, session=None, proxies=None, headers=None):
        self.api_key = aicm_api_key
        self.api_base = "http://x"
        self.api_url = "/api"
        self.session = session or DummySession()
        self.ini_path = "ini"

    monkeypatch.setattr(AsyncCostManagerClient, "__init__", fake_async_init)
    monkeypatch.setattr(CostManagerClient, "__init__", fake_sync_init)

    async def run():
        manager = AsyncClientCostManager(
            DummyClient(), client_customer_key="c1", context={"foo": "bar"}
        )
        await manager.add(a=1, b=2)
        manager.set_client_customer_key("c2")
        manager.set_context({"baz": "qux"})
        await manager.add(a=2, b=3)
        payloads = manager.get_tracked_payloads()
        assert payloads[0]["client_customer_key"] == "c1"
        assert payloads[0]["context"] == {"foo": "bar"}
        assert payloads[1]["client_customer_key"] == "c2"
        assert payloads[1]["context"] == {"baz": "qux"}
        await manager.stop_delivery()

    asyncio.run(run())
