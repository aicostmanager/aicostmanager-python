import pytest

from aicostmanager.client import CostManagerClient
from aicostmanager.config_manager import Config, CostManagerConfig
from aicostmanager.cost_manager import CostManager


class DummyClient:
    def add(self, *, a, b):
        return a + b


class DummySession:
    def __init__(self):
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        return object()


def reset_global():
    from aicostmanager import delivery as mod

    mod._global_delivery = None


@pytest.fixture(autouse=True)
def set_key(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    yield


def test_cost_manager_queues_payload(monkeypatch, tmp_path):
    reset_global()
    session = DummySession()

    def fake_init(
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
        self.ini_path = aicm_ini_path or str(tmp_path / "test_ini")

    session_obj = session
    monkeypatch.setattr(CostManagerClient, "__init__", fake_init)

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

    manager = CostManager(DummyClient(), delivery_queue_size=10)
    manager.add(a=2, b=3)

    manager.delivery._queue.join()
    manager.stop_delivery()

    assert len(session.calls) == 1
    assert session.calls[0][1]["usage_records"][0]["usage"] == 5
