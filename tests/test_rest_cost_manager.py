import asyncio
import pytest

from aicostmanager.config_manager import Config, CostManagerConfig
from aicostmanager.rest_cost_manager import RestCostManager, AsyncRestCostManager
from aicostmanager.client import CostManagerClient, AsyncCostManagerClient


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
            "response_fields": [{"key": "value", "path": ""}],
            "payload_mapping": {
                "config": "config_identifier",
                "timestamp": "timestamp",
                "usage": "response_data.value",
            },
        },
    )
    monkeypatch.setattr(CostManagerConfig, "get_config", lambda self, api_id: [cfg])


class DummyClientInit:
    def __init__(self, *, aicm_api_key=None, aicm_api_base=None, aicm_api_url=None, aicm_ini_path=None, session=None, proxies=None, headers=None):
        self.api_key = aicm_api_key
        self.api_base = "http://x"
        self.api_url = "/api"
        self.session = session or DummySession()
        self.ini_path = "ini"


class DummyAsyncClientInit:
    def __init__(self, *, aicm_api_key=None, aicm_api_base=None, aicm_api_url=None, aicm_ini_path=None, session=None, proxies=None, headers=None):
        self.api_key = aicm_api_key
        self.api_base = "http://x"
        self.api_url = "/api"
        self.session = session or DummyAsyncSession()
        self.ini_path = "ini"


def test_rest_manager_tracks(monkeypatch, config):
    monkeypatch.setattr(CostManagerClient, "__init__", DummyClientInit.__init__)
    session = DummySession()
    manager = RestCostManager(session, base_url="https://api.example.com")
    resp = manager.get("/foo")
    assert resp.json() == {"value": 5}
    payloads = manager.get_tracked_payloads()
    assert len(payloads) == 1
    assert payloads[0]["usage"] == 5


def test_async_rest_manager_tracks(monkeypatch, config):
    monkeypatch.setattr(AsyncCostManagerClient, "__init__", DummyAsyncClientInit.__init__)
    monkeypatch.setattr(CostManagerClient, "__init__", DummyClientInit.__init__)

    async def run():
        session = DummyAsyncSession()
        manager = AsyncRestCostManager(session, base_url="https://api.example.com")
        resp = await manager.get("/foo")
        assert resp.json() == {"value": 5}
        payloads = manager.get_tracked_payloads()
        assert len(payloads) == 1
        assert payloads[0]["usage"] == 5
        await manager.stop_delivery()

    asyncio.run(run())
