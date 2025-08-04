import pytest

from aicostmanager.config_manager import Config, CostManagerConfig
from aicostmanager.cost_manager import CostManager


class DummyClient:
    def add(self, *, a, b):
        return a + b


@pytest.fixture(autouse=True)
def set_key(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    yield


def test_manager_tracks(monkeypatch):
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
    manager = CostManager(DummyClient())
    result = manager.add(a=2, b=3)
    assert result == 5
    payloads = manager.get_tracked_payloads()
    assert len(payloads) == 1
    assert payloads[0]["config"] == "dummy"
    assert payloads[0]["usage"] == 5


def test_context_manager(monkeypatch):
    monkeypatch.setattr(CostManagerConfig, "get_config", lambda self, api_id: [])
    dummy = DummyClient()
    calls = {"start": 0, "stop": 0}

    class DummyDelivery:
        def start(self):
            calls["start"] += 1

        def stop(self):
            calls["stop"] += 1

        def deliver(self, payload):
            pass

    manager = CostManager(dummy, delivery=DummyDelivery())
    with manager as m:
        assert m is manager
    assert calls["start"] == 1
    assert calls["stop"] == 1


def test_client_customer_key_and_context(monkeypatch):
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

    manager = CostManager(
        DummyClient(), client_customer_key="c1", context={"foo": "bar"}
    )
    manager.add(a=1, b=2)
    manager.set_client_customer_key("c2")
    manager.set_context({"baz": "qux"})
    manager.add(a=2, b=3)
    payloads = manager.get_tracked_payloads()
    assert payloads[0]["client_customer_key"] == "c1"
    assert payloads[0]["context"] == {"foo": "bar"}
    assert payloads[1]["client_customer_key"] == "c2"
    assert payloads[1]["context"] == {"baz": "qux"}
