import pathlib
import time
import jwt

from aicostmanager.client import CostManagerClient
from aicostmanager.config_manager import ConfigManager
from aicostmanager.limits import TriggeredLimitManager, UsageLimitManager
from aicostmanager.models import (
    UsageLimitIn,
    UsageLimitOut,
    UsageLimitProgressOut,
    ThresholdType,
    Period,
)

PRIVATE_KEY = (pathlib.Path(__file__).parent / "threshold_private_key.pem").read_text()
PUBLIC_KEY = (pathlib.Path(__file__).parent / "threshold_public_key.pem").read_text()


def _make_triggered_limits():
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
        "client_customer_key": "api-key-customer",
        "api_key_id": "550e8400-e29b-41d4-a716-446655440000",
        "triggered_at": "2024-12-31T18:00:00Z",
        "expires_at": "2025-01-01T18:00:00Z",
    }
    payload = {
        "iss": "aicm-api",
        "sub": "550e8400-e29b-41d4-a716-446655440000",
        "iat": now,
        "jti": "tl",
        "version": "v1",
        "key_id": "test",
        "triggered_limits": [event],
    }
    token = jwt.encode(payload, PRIVATE_KEY, algorithm="RS256", headers={"kid": "test"})
    item = {"version": "v1", "public_key": PUBLIC_KEY, "key_id": "test", "encrypted_payload": token}
    return item, event


def test_update_and_check(monkeypatch, tmp_path):
    ini = tmp_path / "AICM.ini"
    client = CostManagerClient(aicm_api_key="sk-test", aicm_ini_path=str(ini))
    cfg_mgr = ConfigManager(client)
    tl_mgr = TriggeredLimitManager(client, cfg_mgr)

    item, event = _make_triggered_limits()
    monkeypatch.setattr(client, "get_triggered_limits", lambda: item)

    tl_mgr.update_triggered_limits()

    stored = cfg_mgr.read_triggered_limits()
    assert stored.get("encrypted_payload") == item["encrypted_payload"]

    cfg_matches = cfg_mgr.get_triggered_limits(service_key=event["service_key"])
    assert len(cfg_matches) == 1

    matches = tl_mgr.check_triggered_limits(
        api_key_id=event["api_key_id"], service_key=event["service_key"]
    )
    assert len(matches) == 1
    assert matches[0].limit_id == event["limit_id"]

    no_match = tl_mgr.check_triggered_limits(
        api_key_id=event["api_key_id"], service_key="other-service"
    )
    assert no_match == []

    wrong_api = tl_mgr.check_triggered_limits(api_key_id="different")
    assert wrong_api == []


def test_usage_limit_management(monkeypatch, tmp_path):
    ini = tmp_path / "AICM.ini"
    client = CostManagerClient(aicm_api_key="sk-test", aicm_ini_path=str(ini))
    ul_mgr = UsageLimitManager(client)

    limit = UsageLimitOut(
        uuid="lim1",
        threshold_type=ThresholdType.LIMIT,
        amount=1,
        period=Period.DAY,
        vendor=None,
        service=None,
        client=None,
        team_uuid="team1",
        user_uuid=None,
        api_key_uuid=None,
        notification_list=None,
        active=True,
    )

    progress = UsageLimitProgressOut(
        **limit.model_dump(),
        current_spend=0,
        remaining_amount=1,
    )

    monkeypatch.setattr(client, "list_usage_limits", lambda: [limit])
    assert ul_mgr.list_usage_limits()[0].uuid == "lim1"

    new_limit = UsageLimitIn(
        threshold_type=ThresholdType.LIMIT,
        amount=1,
        period=Period.DAY,
        team_uuid="team1",
    )
    monkeypatch.setattr(client, "create_usage_limit", lambda data: limit)
    assert ul_mgr.create_usage_limit(new_limit).uuid == "lim1"

    monkeypatch.setattr(client, "get_usage_limit", lambda lid: limit)
    assert ul_mgr.get_usage_limit("lim1").uuid == "lim1"

    updated = limit.model_copy(update={"amount": 2})
    monkeypatch.setattr(client, "update_usage_limit", lambda lid, data: updated)
    assert ul_mgr.update_usage_limit("lim1", new_limit).amount == 2

    called = {}

    def _delete(lid):
        called["id"] = lid

    monkeypatch.setattr(client, "delete_usage_limit", _delete)
    ul_mgr.delete_usage_limit("lim1")
    assert called["id"] == "lim1"

    monkeypatch.setattr(client, "list_usage_limit_progress", lambda: [progress])
    assert ul_mgr.list_usage_limit_progress()[0].current_spend == 0
