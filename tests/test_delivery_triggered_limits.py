import pathlib
import time

import jwt
import pytest

from aicostmanager.client.exceptions import UsageLimitExceeded
from aicostmanager.config_manager import ConfigManager
from aicostmanager.delivery import DeliveryConfig
from aicostmanager.delivery.immediate import ImmediateDelivery
from aicostmanager.ini_manager import IniManager

PRIVATE_KEY = (pathlib.Path(__file__).parent / "threshold_private_key.pem").read_text()
PUBLIC_KEY = (pathlib.Path(__file__).parent / "threshold_public_key.pem").read_text()


def _setup_triggered_limits(ini_path):
    now = int(time.time())
    event = {
        "event_id": "evt-api-key-limit",
        "limit_id": "lmt-api-key-limit",
        "threshold_type": "limit",
        "amount": 100.0,
        "period": "month",
        "limit_context": "key",
        "limit_message": "Usage limit exceeded",
        "service_key": "openai::gpt-4",
        "customer_key": "api-key-customer",
        "api_key_id": "550e8400-e29b-41d4-a716-446655440000",
        "triggered_at": "2024-12-31T18:00:00Z",
        "expires_at": "2025-01-01T18:00:00Z",
    }
    payload = {
        "iss": "aicm-api",
        "sub": event["api_key_id"],
        "iat": now,
        "jti": "tl",
        "version": "v1",
        "key_id": "test",
        "triggered_limits": [event],
    }
    token = jwt.encode(payload, PRIVATE_KEY, algorithm="RS256", headers={"kid": "test"})
    item = {
        "version": "v1",
        "public_key": PUBLIC_KEY,
        "key_id": "test",
        "encrypted_payload": token,
    }
    cfg = ConfigManager(ini_path=str(ini_path))
    cfg.write_triggered_limits(item)
    IniManager(str(ini_path)).set_option("tracker", "AICM_LIMITS_ENABLED", "true")
    return event


def test_immediate_enforce_triggered_limit(tmp_path):
    ini = tmp_path / "AICM.ini"
    event = _setup_triggered_limits(ini)
    config = DeliveryConfig(
        ini_manager=IniManager(str(ini)), aicm_api_key=event["api_key_id"]
    )
    delivery = ImmediateDelivery(config)
    called = {}

    def fake_post(body, max_attempts):
        called["called"] = True
        return {
            "results": [{"response_id": "r1", "cost_events": [{"x": 1}]}],
            "triggered_limits": {},
        }

    delivery._post_with_retry = fake_post

    payload = {
        "api_id": "openai",
        "service_key": event["service_key"],
        "customer_key": event["customer_key"],
        "payload": {},
    }
    with pytest.raises(UsageLimitExceeded):
        delivery.enqueue(payload)
    assert called.get("called")


def test_triggered_limits_cached_in_memory(tmp_path, monkeypatch):
    ini = tmp_path / "AICM.ini"
    event = _setup_triggered_limits(ini)
    config = DeliveryConfig(
        ini_manager=IniManager(str(ini)), aicm_api_key=event["api_key_id"]
    )
    delivery = ImmediateDelivery(config)

    def fake_post(body, max_attempts):
        return {
            "results": [{"response_id": "r1", "cost_events": [{"x": 1}]}],
            "triggered_limits": {},
        }

    delivery._post_with_retry = fake_post
    payload = {
        "api_id": "openai",
        "service_key": event["service_key"],
        "customer_key": event["customer_key"],
        "payload": {},
    }
    with pytest.raises(UsageLimitExceeded):
        delivery.enqueue(payload)

    def fail_read(self):
        raise AssertionError("read_triggered_limits should not be called")

    monkeypatch.setattr(ConfigManager, "read_triggered_limits", fail_read)

    with pytest.raises(UsageLimitExceeded):
        delivery.enqueue(payload)
