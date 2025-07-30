import pytest

from aicostmanager.client import (
    APIRequestError,
    CostManagerClient,
)


def make_client(aicm_api_key, aicm_api_base, aicm_ini_path):
    return CostManagerClient(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )


def test_env_var_configuration(aicm_api_key, aicm_api_base, aicm_ini_path):
    client = make_client(aicm_api_key, aicm_api_base, aicm_ini_path)
    assert client.api_key == aicm_api_key
    assert client.api_base == aicm_api_base
    assert client.ini_path == aicm_ini_path


def test_default_ini_path(aicm_api_key, aicm_api_base, aicm_ini_path):
    client = make_client(aicm_api_key, aicm_api_base, aicm_ini_path)
    assert client.ini_path.endswith("AICM.INI")


def test_methods(aicm_api_key, aicm_api_base, aicm_ini_path):
    client = make_client(aicm_api_key, aicm_api_base, aicm_ini_path)
    # Only test endpoints that are safe and do not mutate data
    client.get_configs()
    client.list_usage_events(limit=1)
    client.list_usage_rollups()
    client.list_customers()
    client.list_usage_limits()
    client.get_openapi_schema()


def test_error_response(aicm_api_key, aicm_api_base, aicm_ini_path):
    client = make_client(aicm_api_key, aicm_api_base, aicm_ini_path)
    # Purposely use a bad event id to trigger error
    with pytest.raises(APIRequestError):
        client.get_usage_event("nonexistent-event-id")
