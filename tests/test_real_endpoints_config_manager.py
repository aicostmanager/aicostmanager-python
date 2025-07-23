import configparser

import pytest
from aicostmanager.client import CostManagerClient
from aicostmanager.config_manager import ConfigNotFound, CostManagerConfig


def make_client(aicm_api_key, aicm_api_base, aicm_ini_path):
    return CostManagerClient(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )


def test_get_config_and_limits(aicm_api_key, aicm_api_base, aicm_ini_path):
    client = make_client(aicm_api_key, aicm_api_base, aicm_ini_path)
    cfg_mgr = CostManagerConfig(client)
    configs = client.get_configs().service_configs
    if not configs:
        pytest.skip("No service configs available for this API key")
    config_id = configs[0].config_id
    result = cfg_mgr.get_config(config_id)
    assert len(result) >= 1
    # Test triggered limits (may be empty)
    cfg_mgr.get_triggered_limits()
    # file written
    cp = configparser.ConfigParser()
    cp.read(aicm_ini_path)
    assert cp.has_section("configs")
    assert cp.has_section("triggered_limits")


def test_config_not_found(aicm_api_key, aicm_api_base, aicm_ini_path):
    client = make_client(aicm_api_key, aicm_api_base, aicm_ini_path)
    cfg_mgr = CostManagerConfig(client)
    with pytest.raises(ConfigNotFound):
        cfg_mgr.get_config("missing-nonexistent-config-id")


def test_get_triggered_limits_empty(aicm_api_key, aicm_api_base, aicm_ini_path):
    client = make_client(aicm_api_key, aicm_api_base, aicm_ini_path)
    cfg_mgr = CostManagerConfig(client)
    # This should not raise, even if there are no triggered limits
    cfg_mgr.get_triggered_limits()
