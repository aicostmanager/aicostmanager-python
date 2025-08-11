import asyncio
import pytest

from aicostmanager.config_manager import Config, CostManagerConfig
from aicostmanager.tracker import Tracker, UsageValidationError


class DummyDelivery:
    def __init__(self):
        self.payloads = []

    def deliver(self, payload):
        self.payloads.append(payload)


class StopDelivery(DummyDelivery):
    def __init__(self):
        super().__init__()
        self.stopped = False

    def stop(self):
        self.stopped = True


def test_tracker_valid_usage(monkeypatch):
    cfg = Config(
        uuid="u",
        config_id="cfg",
        api_id="api",
        last_updated="now",
        handling_config={},
        manual_usage_schema={"tokens": "int", "model": "str"},
    )

    def fake_get_config_by_id(self, config_id):
        return cfg

    monkeypatch.setattr(CostManagerConfig, "get_config_by_id", fake_get_config_by_id)
    delivery = DummyDelivery()
    tracker = Tracker("cfg", "svc", aicm_api_key="sk-test", delivery=delivery)

    tracker.track({"tokens": 10, "model": "gpt"})
    assert len(delivery.payloads) == 1
    record = delivery.payloads[0]["usage_records"][0]
    assert record["usage"]["tokens"] == 10
    assert record["service_id"] == "svc"


def test_tracker_custom_response_id(monkeypatch):
    cfg = Config(
        uuid="u",
        config_id="cfg",
        api_id="api",
        last_updated="now",
        handling_config={},
        manual_usage_schema={"tokens": "int", "model": "str"},
    )

    def fake_get_config_by_id(self, config_id):
        return cfg

    monkeypatch.setattr(CostManagerConfig, "get_config_by_id", fake_get_config_by_id)
    delivery = DummyDelivery()
    tracker = Tracker("cfg", "svc", aicm_api_key="sk-test", delivery=delivery)

    tracker.track({"tokens": 10, "model": "gpt"}, response_id="session123")
    record = delivery.payloads[0]["usage_records"][0]
    assert record["response_id"] == "session123"


def test_tracker_custom_timestamp(monkeypatch):
    cfg = Config(
        uuid="u",
        config_id="cfg",
        api_id="api",
        last_updated="now",
        handling_config={},
        manual_usage_schema={"tokens": "int", "model": "str"},
    )

    def fake_get_config_by_id(self, config_id):
        return cfg

    monkeypatch.setattr(CostManagerConfig, "get_config_by_id", fake_get_config_by_id)
    delivery = DummyDelivery()
    tracker = Tracker("cfg", "svc", aicm_api_key="sk-test", delivery=delivery)

    tracker.track(
        {"tokens": 10, "model": "gpt"}, timestamp="2024-01-01T00:00:00Z"
    )
    record = delivery.payloads[0]["usage_records"][0]
    assert record["timestamp"] == "2024-01-01T00:00:00Z"


def test_tracker_invalid_usage(monkeypatch):
    cfg = Config(
        uuid="u",
        config_id="cfg",
        api_id="api",
        last_updated="now",
        handling_config={},
        manual_usage_schema={"tokens": "int"},
    )

    def fake_get_config_by_id(self, config_id):
        return cfg

    monkeypatch.setattr(CostManagerConfig, "get_config_by_id", fake_get_config_by_id)
    tracker = Tracker("cfg", "svc", aicm_api_key="sk-test", delivery=DummyDelivery())

    with pytest.raises(UsageValidationError):
        tracker.track({"tokens": "wrong"})


def test_tracker_async_factory(monkeypatch):
    cfg = Config(
        uuid="u",
        config_id="cfg",
        api_id="api",
        last_updated="now",
        handling_config={},
        manual_usage_schema={"tokens": "int", "model": "str"},
    )

    def fake_get_config_by_id(self, config_id):
        return cfg

    monkeypatch.setattr(CostManagerConfig, "get_config_by_id", fake_get_config_by_id)
    delivery = DummyDelivery()

    async def run() -> None:
        tracker = await Tracker.create_async(
            "cfg", "svc", aicm_api_key="sk-test", delivery=delivery
        )
        tracker.track({"tokens": 10, "model": "gpt"})
        assert len(delivery.payloads) == 1

    asyncio.run(run())


def test_tracker_close(monkeypatch):
    cfg = Config(
        uuid="u",
        config_id="cfg",
        api_id="api",
        last_updated="now",
        handling_config={},
        manual_usage_schema={}
    )

    def fake_get_config_by_id(self, config_id):
        return cfg

    monkeypatch.setattr(CostManagerConfig, "get_config_by_id", fake_get_config_by_id)
    delivery = StopDelivery()
    tracker = Tracker("cfg", "svc", aicm_api_key="sk-test", delivery=delivery)

    tracker.close()
    assert delivery.stopped
