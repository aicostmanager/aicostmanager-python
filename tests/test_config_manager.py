import configparser
import pathlib
import time

import jwt
import pytest

from aicostmanager.client import CostManagerClient
from aicostmanager.config_manager import ConfigNotFound, CostManagerConfig

PRIVATE_KEY = (pathlib.Path(__file__).parent / "threshold_private_key.pem").read_text()
PUBLIC_KEY = (pathlib.Path(__file__).parent / "threshold_public_key.pem").read_text()


def _make_config_item(api_id: str = "python-client"):
    now = int(time.time())
    cfg_payload = {
        "uuid": "cfg-1",
        "config_id": api_id,
        "api_id": api_id,
        "last_updated": "2025-01-01T00:00:00Z",
        "handling_config": {"foo": "bar"},
    }
    payload = {
        "iss": "aicm-api",
        "sub": "api-key-id",
        "iat": now,
        "exp": now + 3600,
        "jti": "config",
        "version": "v1",
        "key_id": "test",
        "configs": [cfg_payload],
    }
    token = jwt.encode(payload, PRIVATE_KEY, algorithm="RS256", headers={"kid": "test"})
    item = {
        "config_id": api_id,
        "api_id": api_id,
        "version": "v1",
        "public_key": PUBLIC_KEY,
        "key_id": "test",
        "encrypted_payload": token,
    }
    return item, cfg_payload


def _make_triggered_limits():
    now = int(time.time())
    event = {
        "event_id": "evt-1",
        "limit_id": "lim-1",
        "threshold_type": "limit",
        "amount": 10.0,
        "period": "day",
        "vendor": {
            "name": "openai",
            "config_ids": ["cfg1"],
            "hostname": "api.openai.com",
        },
        "service_id": "gpt-4",
        "client_customer_key": "cust1",
        "api_key_id": "api-key-id",
        "triggered_at": "2025-01-01T00:00:00Z",
        "expires_at": "2025-01-02T00:00:00Z",
    }
    payload = {
        "iss": "aicm-api",
        "sub": "api-key-id",
        "iat": now,
        "exp": now + 3600,
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
    return item, [event]


def test_get_config_and_limits(monkeypatch, tmp_path):
    ini = tmp_path / "AICM.ini"
    client = CostManagerClient(aicm_api_key="sk-test", aicm_ini_path=str(ini))
    cfg_mgr = CostManagerConfig(client)

    config_item, cfg_payload = _make_config_item()
    tl_item, tl_events = _make_triggered_limits()

    def fake_get_configs():
        return {"service_configs": [config_item], "triggered_limits": tl_item}

    monkeypatch.setattr(client, "get_configs", fake_get_configs)

    configs = cfg_mgr.get_config("python-client")
    assert len(configs) == 1
    assert configs[0].handling_config == cfg_payload["handling_config"]

    limits = cfg_mgr.get_triggered_limits(service_id="gpt-4")
    assert len(limits) == 1
    assert limits[0].service_id == "gpt-4"
    assert limits[0].config_id_list == ["cfg1"]
    assert limits[0].hostname == "api.openai.com"

    # file written
    cp = configparser.ConfigParser()
    cp.read(ini)
    assert cp.has_section("configs")
    assert cp.has_section("triggered_limits")


def test_config_not_found(monkeypatch, tmp_path):
    ini = tmp_path / "AICM.ini"
    client = CostManagerClient(aicm_api_key="sk-test", aicm_ini_path=str(ini))
    cfg_mgr = CostManagerConfig(client)

    config_item, _ = _make_config_item("other")
    tl_item, _ = _make_triggered_limits()
    monkeypatch.setattr(
        client,
        "get_configs",
        lambda: {"service_configs": [config_item], "triggered_limits": tl_item},
    )

    with pytest.raises(ConfigNotFound):
        cfg_mgr.get_config("missing")


def test_get_triggered_limits_empty(monkeypatch, tmp_path):
    ini = tmp_path / "AICM.ini"
    client = CostManagerClient(aicm_api_key="sk-test", aicm_ini_path=str(ini))
    cfg_mgr = CostManagerConfig(client)

    config_item, _ = _make_config_item()
    now = int(time.time())
    payload = {
        "iss": "aicm-api",
        "sub": "api-key-id",
        "iat": now,
        "exp": now + 3600,
        "jti": "tl",
        "version": "v1",
        "key_id": "test",
        "triggered_limits": [],
    }
    token = jwt.encode(payload, PRIVATE_KEY, algorithm="RS256", headers={"kid": "test"})
    tl_item = {
        "version": "v1",
        "public_key": PUBLIC_KEY,
        "key_id": "test",
        "encrypted_payload": token,
    }
    monkeypatch.setattr(
        client,
        "get_configs",
        lambda: {"service_configs": [config_item], "triggered_limits": tl_item},
    )

    limits = cfg_mgr.get_triggered_limits()
    assert limits == []


def test_refresh_and_auto(monkeypatch, tmp_path):
    ini = tmp_path / "AICM.ini"
    client = CostManagerClient(aicm_api_key="sk", aicm_ini_path=str(ini))
    cfg_mgr = CostManagerConfig(client, auto_refresh=True)

    called = {}

    def fake_get_configs():
        called["count"] = called.get("count", 0) + 1
        item, _ = _make_config_item()
        tl_item, _ = _make_triggered_limits()
        return {"service_configs": [item], "triggered_limits": tl_item}

    monkeypatch.setattr(client, "get_configs", fake_get_configs)

    cfg_mgr.refresh()
    assert called["count"] == 1
    cfg_mgr.get_config("python-client")
    assert called["count"] == 2  # auto refresh triggered
