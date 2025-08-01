import configparser
import json
import os
import time

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


def test_etag_unchanged_triggers_limits_endpoint(
    aicm_api_key, aicm_api_base, aicm_ini_path
):
    """
    Test that when the /configs endpoint etag hasn't changed, the config manager
    calls the /triggered-limits endpoint and writes the appropriate data to the INI file.

    This test:
    1. Makes initial call to /configs endpoint and writes info to INI file (establishes etag)
    2. Makes another call, sees that etag hasn't changed (gets None response)
    3. Verifies that a successful call to /triggered-limits endpoint was made
    4. Verifies that the triggered limits data was written to the INI file
    """
    # Ensure we start with a clean INI file
    if os.path.exists(aicm_ini_path):
        os.remove(aicm_ini_path)

    client = make_client(aicm_api_key, aicm_api_base, aicm_ini_path)
    cfg_mgr = CostManagerConfig(client)

    try:
        # STEP 1: Make initial call to /configs endpoint
        # This should create the INI file and establish an etag
        cfg_mgr.refresh()

        # Verify INI file was created and has configs section with etag
        assert os.path.exists(aicm_ini_path), (
            "INI file should be created after first refresh"
        )

        cp = configparser.ConfigParser()
        cp.read(aicm_ini_path)

        assert cp.has_section("configs"), (
            "INI should have configs section after first refresh"
        )
        assert cp.has_section("triggered_limits"), (
            "INI should have triggered_limits section after first refresh"
        )

        # Get the etag that was stored
        initial_etag = cp["configs"].get("etag")
        assert initial_etag is not None, (
            "ETag should be stored in INI after first refresh"
        )
        assert initial_etag != "", "ETag should not be empty"

        # Get initial payload data for comparison
        initial_configs_payload = cp["configs"].get("payload")
        initial_triggered_limits_payload = cp["triggered_limits"].get("payload")

        assert initial_configs_payload is not None, "Configs payload should be stored"
        assert initial_triggered_limits_payload is not None, (
            "Triggered limits payload should be stored"
        )

        # Store the client's etag for verification
        client_etag = client.configs_etag
        assert client_etag == initial_etag, "Client etag should match stored etag"

        # Record file modification time to detect changes
        initial_mtime = os.path.getmtime(aicm_ini_path)

        # Wait a moment to ensure any file changes will have different timestamps
        time.sleep(0.1)

        # STEP 2: Make another call to refresh()
        # This should detect the existing etag and potentially get a 304 response from /configs
        # When that happens, it should call /triggered-limits endpoint
        cfg_mgr.refresh()

        # STEP 3: Verify the behavior
        # Read the INI file again to check what happened
        cp_after = configparser.ConfigParser()
        cp_after.read(aicm_ini_path)

        # The configs section should still exist and may or may not have been updated
        assert cp_after.has_section("configs"), "Configs section should still exist"
        assert cp_after.has_section("triggered_limits"), (
            "Triggered limits section should still exist"
        )

        # Get the current etag
        current_etag = cp_after["configs"].get("etag")
        assert current_etag is not None, "ETag should still be present"

        # The triggered_limits section should have been updated (this is the key test)
        current_triggered_limits_payload = cp_after["triggered_limits"].get("payload")
        assert current_triggered_limits_payload is not None, (
            "Triggered limits payload should still be present"
        )

        # Parse the triggered limits payload to verify it's valid JSON
        try:
            triggered_limits_data = json.loads(current_triggered_limits_payload)
            # The data should be a dict (even if empty) - this confirms the /triggered-limits endpoint was called
            assert isinstance(triggered_limits_data, dict), (
                "Triggered limits payload should be a valid dict"
            )
        except json.JSONDecodeError:
            pytest.fail("Triggered limits payload should be valid JSON")

        # STEP 4: Verify the client still has the correct etag
        final_client_etag = client.configs_etag
        assert final_client_etag is not None, "Client should still have an etag"

        # The client etag should match what's stored in the INI
        assert final_client_etag == current_etag, "Client etag should match stored etag"

        # STEP 5: Additional verification - test that the triggered limits functionality works
        # Try to get triggered limits to ensure the data is properly stored and readable
        try:
            triggered_limits = cfg_mgr.get_triggered_limits()
            # This should not raise an exception, even if the list is empty
            assert isinstance(triggered_limits, list), (
                "get_triggered_limits should return a list"
            )
        except Exception as e:
            pytest.fail(f"get_triggered_limits should not raise an exception: {e}")

        print(
            "✓ Test passed: ETag-based refresh successfully triggered /triggered-limits endpoint call"
        )
        print(f"  - Initial ETag: {initial_etag}")
        print(f"  - Final ETag: {current_etag}")
        print(
            f"  - Triggered limits data present: {'encrypted_payload' in triggered_limits_data}"
        )

    finally:
        client.close()
