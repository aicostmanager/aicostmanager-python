import pytest

from aicostmanager.config_manager import Config, CostManagerConfig
from aicostmanager.cost_manager import CostManager


class DummyClient:
    def add(self, a, b):
        return a + b

    def stream(self):
        for i in range(3):
            yield i


@pytest.fixture(autouse=True)
def set_key(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    yield


def test_tracker_loads_configs(monkeypatch):
    dummy = DummyClient()
    cfg = Config(
        uuid="cfg-1",
        config_id="dummy",
        api_id="dummyclient",
        last_updated="2025-01-01T00:00:00Z",
        handling_config={"x": 1},
    )

    called = {}

    def fake_get_config(self, api_id):
        called["api_id"] = api_id
        return [cfg]

    monkeypatch.setattr(CostManagerConfig, "get_config", fake_get_config)

    tracker = CostManager(dummy)

    assert tracker.api_id == "test_cost_manager_wrapper"
    assert tracker.configs == [cfg]
    assert called["api_id"] == "test_cost_manager_wrapper"


def test_passthrough_method(monkeypatch):
    monkeypatch.setattr(CostManagerConfig, "get_config", lambda self, api_id: [])
    monkeypatch.setattr(
        CostManagerConfig, "get_triggered_limits", lambda self, **kwargs: []
    )
    tracker = CostManager(DummyClient())
    assert tracker.add(2, 3) == 5


def test_passthrough_streaming(monkeypatch):
    monkeypatch.setattr(CostManagerConfig, "get_config", lambda self, api_id: [])
    monkeypatch.setattr(
        CostManagerConfig, "get_triggered_limits", lambda self, **kwargs: []
    )
    tracker = CostManager(DummyClient())
    assert list(tracker.stream()) == [0, 1, 2]


def test_limits_checked_on_access(monkeypatch):
    class Dummy:
        value = 1

        def add(self, a, b):
            return a + b

    calls = {"count": 0}

    monkeypatch.setattr(CostManagerConfig, "get_config", lambda self, api_id: [])

    def fake_get_limits(self, **kwargs):
        calls["count"] += 1
        return []

    monkeypatch.setattr(CostManagerConfig, "get_triggered_limits", fake_get_limits)

    tracker = CostManager(Dummy())
    tracker.add(1, 2)
    _ = tracker.value
    tracker.add(3, 4)

    assert calls["count"] == 3
