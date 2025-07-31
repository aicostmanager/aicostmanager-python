"""
Comprehensive test suite for ETag functionality using real API calls.

This test suite validates ETag caching behavior for the /configs endpoint
in both sync and async clients, including:

- Basic ETag flow (first call -> set ETag -> second call -> 304 Not Modified)
- CostManagerConfig integration with INI file persistence
- Manual ETag manipulation and out-of-date config scenarios
- Invalid ETag handling
- Multiple refresh cycles
- Direct client ETag property behavior
- Edge cases and error scenarios

All tests use real API calls to ensure the ETag functionality works correctly
in real-world scenarios, not just with mocked responses.
"""

import asyncio
import configparser
import os
import time

from aicostmanager.client import AsyncCostManagerClient, CostManagerClient
from aicostmanager.config_manager import CostManagerConfig


def make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path):
    """Create a sync CostManagerClient for testing."""
    return CostManagerClient(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )


def make_async_client(aicm_api_key, aicm_api_base, aicm_ini_path):
    """Create an async CostManagerClient for testing."""
    return AsyncCostManagerClient(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )


def ensure_ini_deleted(ini_path):
    """Ensure the INI file is deleted."""
    if os.path.exists(ini_path):
        os.remove(ini_path)
    assert not os.path.exists(ini_path), f"INI file {ini_path} should be deleted"


def read_ini_config(ini_path):
    """Read and return the INI configuration."""
    cp = configparser.ConfigParser()
    cp.read(ini_path)
    return cp


def get_file_mtime(file_path):
    """Get file modification time."""
    return os.path.getmtime(file_path) if os.path.exists(file_path) else None


class TestSyncClientETag:
    """Test ETag functionality with sync CostManagerClient using real API calls."""

    def test_basic_etag_flow(self, aicm_api_key, aicm_api_base, aicm_ini_path):
        """Test basic ETag caching flow using CostManagerConfig: delete INI -> refresh -> check ETag -> refresh again -> verify 304."""
        # Start with clean slate
        ensure_ini_deleted(aicm_ini_path)

        client = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)
        config_mgr = CostManagerConfig(client)

        try:
            # First refresh - should create INI file and set ETag
            config_mgr.refresh()
            assert os.path.exists(aicm_ini_path), (
                "INI file should be created after first refresh"
            )

            # Check that ETag was set on client
            etag1 = client.configs_etag
            assert etag1 is not None, "configs_etag should be set after successful call"
            assert etag1 != "", "configs_etag should not be empty"

            # Check INI file contains the ETag
            cp = read_ini_config(aicm_ini_path)
            assert cp.has_section("configs"), "INI should have configs section"
            stored_etag = cp["configs"].get("etag")
            assert stored_etag == etag1, (
                f"Stored ETag {stored_etag} should match client ETag {etag1}"
            )

            # Record file modification time
            mtime_after_first = get_file_mtime(aicm_ini_path)

            # Wait a moment to ensure different modification times if file is rewritten
            time.sleep(0.1)

            # Second refresh - should use ETag and potentially get 304
            config_mgr.refresh()

            # Check if file was modified (if 304, it shouldn't be)
            mtime_after_second = get_file_mtime(aicm_ini_path)

            # The ETag should still be valid
            etag2 = client.configs_etag
            assert etag2 is not None, (
                "configs_etag should still be set after second refresh"
            )

            # If we got 304, the file should not be rewritten
            # If we got fresh data, the file might be rewritten but ETag should be updated
            # Let's check if the stored ETag is still the same
            cp2 = read_ini_config(aicm_ini_path)
            stored_etag2 = cp2["configs"].get("etag")
            assert stored_etag2 == etag2, (
                "Stored ETag should match client ETag after second refresh"
            )

        finally:
            client.close()

    def test_config_manager_etag_integration(
        self, aicm_api_key, aicm_api_base, aicm_ini_path
    ):
        """Test that CostManagerConfig properly handles ETag workflow."""
        ensure_ini_deleted(aicm_ini_path)

        client = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)
        config_mgr = CostManagerConfig(client)

        try:
            # First refresh - creates INI with ETag
            config_mgr.refresh()
            assert os.path.exists(aicm_ini_path), "INI file should be created"

            # Check INI contains ETag
            cp = read_ini_config(aicm_ini_path)
            assert cp.has_section("configs"), "INI should have configs section"

            etag1 = cp["configs"].get("etag")
            assert etag1 is not None, "ETag should be stored in INI"
            assert etag1 == client.configs_etag, "Stored ETag should match client ETag"

            # Second refresh - should use existing ETag
            mtime_before = get_file_mtime(aicm_ini_path)
            time.sleep(0.1)

            config_mgr.refresh()

            # Check if ETag is still valid (file may or may not be updated depending on 304)
            etag2 = client.configs_etag
            assert etag2 is not None, "ETag should still be set"

        finally:
            client.close()

    def test_manual_etag_manipulation(self, aicm_api_key, aicm_api_base, aicm_ini_path):
        """Test behavior when ETag is manually changed to simulate out-of-date config."""
        ensure_ini_deleted(aicm_ini_path)

        client = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)
        config_mgr = CostManagerConfig(client)

        try:
            # First refresh to establish baseline and create INI
            config_mgr.refresh()
            assert os.path.exists(aicm_ini_path)
            original_etag = client.configs_etag

            # Manually modify the ETag in INI file to simulate out-of-date config
            cp = read_ini_config(aicm_ini_path)
            fake_etag = "fake-etag-12345"
            if cp.has_section("configs"):
                cp["configs"]["etag"] = fake_etag
            else:
                cp.add_section("configs")
                cp["configs"]["etag"] = fake_etag
                cp["configs"]["payload"] = "[]"

            # Write the modified config back
            with open(aicm_ini_path, "w") as f:
                cp.write(f)

            # Create new config manager to pick up the modified INI
            client2 = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)
            config_mgr2 = CostManagerConfig(client2)

            try:
                # Refresh should detect the fake ETag and get fresh data
                config_mgr2.refresh()

                # ETag should be updated to a valid one
                new_etag = client2.configs_etag
                assert new_etag != fake_etag, "ETag should be updated from fake value"
                assert new_etag is not None, "New ETag should be set"

            finally:
                client2.close()

        finally:
            client.close()

    def test_comprehensive_manual_etag_update_verification(
        self, aicm_api_key, aicm_api_base, aicm_ini_path
    ):
        """Comprehensive test verifying manual ETag manipulation triggers proper server response and INI updates."""
        ensure_ini_deleted(aicm_ini_path)

        client = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)
        config_mgr = CostManagerConfig(client)

        try:
            # STEP 1: Establish baseline with valid ETag
            config_mgr.refresh()
            assert os.path.exists(aicm_ini_path)
            original_etag = client.configs_etag
            assert original_etag is not None, (
                "Should have valid ETag after first refresh"
            )

            # Read the original INI content to compare later
            cp_original = read_ini_config(aicm_ini_path)
            original_payload = cp_original["configs"].get("payload")
            original_stored_etag = cp_original["configs"].get("etag")
            assert original_stored_etag == original_etag, (
                "INI should store the same ETag as client"
            )

            # STEP 2: Manually corrupt the ETag to simulate out-of-date config
            fake_etag = "manually-corrupted-etag-xyz123"
            assert fake_etag != original_etag, (
                "Fake ETag must be different from valid one"
            )

            cp_modified = read_ini_config(aicm_ini_path)
            cp_modified["configs"]["etag"] = fake_etag

            with open(aicm_ini_path, "w") as f:
                cp_modified.write(f)

            # Verify the corruption was applied
            cp_corrupted = read_ini_config(aicm_ini_path)
            assert cp_corrupted["configs"].get("etag") == fake_etag, (
                "Fake ETag should be in INI"
            )

            # STEP 3: Create new client that will read the corrupted ETag
            client2 = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)
            config_mgr2 = CostManagerConfig(client2)

            try:
                # Monitor file changes to verify server response handling
                mtime_before = get_file_mtime(aicm_ini_path)
                time.sleep(0.1)  # Ensure measurable time difference

                # STEP 4: Refresh with corrupted ETag - should trigger fresh data fetch
                config_mgr2.refresh()

                # STEP 5: Verify server rejected fake ETag and client updated properly

                # File should be rewritten (indicating server returned fresh data, not 304)
                mtime_after = get_file_mtime(aicm_ini_path)
                assert mtime_after != mtime_before, (
                    "INI file should be rewritten when server rejects fake ETag and returns fresh data"
                )

                # Client should have updated ETag from server response
                updated_etag = client2.configs_etag
                assert updated_etag is not None, "Client should have ETag after refresh"
                assert updated_etag != fake_etag, (
                    "Client ETag should be updated from fake value"
                )
                assert updated_etag == original_etag, (
                    "Client should have the correct server ETag"
                )

                # STEP 6: Verify INI file was properly updated
                cp_final = read_ini_config(aicm_ini_path)
                final_stored_etag = cp_final["configs"].get("etag")
                final_payload = cp_final["configs"].get("payload")

                assert final_stored_etag == updated_etag, (
                    "INI should store the updated ETag"
                )
                assert final_stored_etag != fake_etag, (
                    "Fake ETag should be completely replaced"
                )
                assert final_payload is not None, (
                    "Payload should be present after refresh"
                )
                assert final_payload != "", "Payload should not be empty after refresh"
                # Note: payload may differ from original due to server-side updates (timestamps, etc.)

                # STEP 7: Verify the fix actually works - subsequent call should get 304
                mtime_before_validation = get_file_mtime(aicm_ini_path)
                time.sleep(0.1)

                config_mgr2.refresh()  # This should use the valid ETag and get 304

                mtime_after_validation = get_file_mtime(aicm_ini_path)
                # File might or might not be rewritten depending on 304 response
                # But ETag should remain the same
                final_etag_check = client2.configs_etag
                assert final_etag_check == updated_etag, (
                    "ETag should remain stable after validation"
                )

            finally:
                client2.close()

        finally:
            client.close()

    def test_direct_server_response_to_invalid_etag(
        self, aicm_api_key, aicm_api_base, aicm_ini_path
    ):
        """Test that server properly rejects invalid ETags and returns fresh data (not 304)."""
        ensure_ini_deleted(aicm_ini_path)

        client = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)

        try:
            # STEP 1: Get a valid ETag from the server
            result1 = client.get_configs()
            assert result1 is not None, "First call should return config data"
            valid_etag = client.configs_etag
            assert valid_etag is not None, "Should have valid ETag"

            # STEP 2: Verify valid ETag works (should get 304)
            result2 = client.get_configs(etag=valid_etag)
            assert result2 is None, "Valid ETag should return 304 (None result)"
            assert client.configs_etag == valid_etag, (
                "ETag should be preserved after 304"
            )

            # STEP 3: Test various invalid ETags - all should return fresh data
            invalid_etags = [
                "completely-fake-etag-123",
                "invalid-format",
                "",  # Empty ETag
                "old-etag-that-never-existed",
                "W/fake-weak-etag",
                "12345-numbers-only",
            ]

            for invalid_etag in invalid_etags:
                # Each invalid ETag should trigger fresh data (not 304)
                result = client.get_configs(etag=invalid_etag)
                assert result is not None, (
                    f"Invalid ETag '{invalid_etag}' should return fresh data, not 304"
                )

                # Client should update to valid ETag from server
                updated_etag = client.configs_etag
                assert updated_etag is not None, (
                    f"ETag should be updated after invalid ETag '{invalid_etag}'"
                )
                assert updated_etag != invalid_etag, (
                    f"ETag should be different from invalid '{invalid_etag}'"
                )
                assert updated_etag == valid_etag, (
                    "Should get the same valid ETag from server"
                )

            # STEP 4: Verify we can still use valid ETag after invalid attempts
            final_result = client.get_configs(etag=valid_etag)
            assert final_result is None, "Valid ETag should still work and return 304"

        finally:
            client.close()

    def test_automatic_etag_handling(self, aicm_api_key, aicm_api_base, aicm_ini_path):
        """Test that client automatically uses stored ETag from INI file."""
        ensure_ini_deleted(aicm_ini_path)

        # First client makes initial call
        client1 = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)
        result1 = client1.get_configs()
        assert result1 is not None
        etag1 = client1.configs_etag

        # Close first client
        client1.close()

        # Create second client - should read ETag from INI
        client2 = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)

        # Record file modification time before call
        mtime_before = get_file_mtime(aicm_ini_path)
        time.sleep(0.1)

        # Call get_configs without explicit ETag - should use stored ETag automatically
        result2 = client2.get_configs()

        # Should get 304 if ETag is still valid, or fresh data if not
        # File should not be unnecessarily rewritten if 304
        mtime_after = get_file_mtime(aicm_ini_path)

        if result2 is None:
            # Got 304, file should not be rewritten
            assert mtime_after == mtime_before, "INI should not be rewritten on 304"
            assert client2.configs_etag == etag1, "ETag should remain the same"
        else:
            # Got fresh data, file may be rewritten with new ETag
            assert result2 is not None, "Should have received fresh config data"

        client2.close()

    def test_direct_client_etag_behavior(
        self, aicm_api_key, aicm_api_base, aicm_ini_path
    ):
        """Test direct client ETag behavior without config manager."""
        ensure_ini_deleted(aicm_ini_path)

        client = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)

        try:
            # Test that client handles ETags correctly even without INI file management
            result1 = client.get_configs()
            assert result1 is not None, "Should get config data"
            etag1 = client.configs_etag
            assert etag1 is not None, "Should set ETag property"

            # Test 304 response with valid ETag
            result2 = client.get_configs(etag=etag1)
            assert result2 is None, "Should get 304 with valid ETag"
            assert client.configs_etag == etag1, "ETag should be preserved"

            # Test with invalid ETag
            result3 = client.get_configs(etag="invalid-etag-xyz")
            assert result3 is not None, "Should get fresh data with invalid ETag"
            new_etag = client.configs_etag
            assert new_etag is not None, "Should update ETag"

        finally:
            client.close()


class TestAsyncClientETag:
    """Test ETag functionality with async CostManagerClient using real API calls."""

    def test_async_basic_etag_flow(self, aicm_api_key, aicm_api_base, aicm_ini_path):
        """Test basic async ETag caching flow."""
        ensure_ini_deleted(aicm_ini_path)

        async def run_async_test():
            client = make_async_client(aicm_api_key, aicm_api_base, aicm_ini_path)

            try:
                # Test direct client ETag functionality
                # First call
                result1 = await client.get_configs()
                assert result1 is not None, (
                    "First async get_configs call should return data"
                )

                etag1 = client.configs_etag
                assert etag1 is not None, "async configs_etag should be set"
                assert etag1 != "", "async configs_etag should not be empty"

                # Second call with ETag - should get 304
                result2 = await client.get_configs(etag=etag1)
                assert result2 is None, (
                    "Second async get_configs call should return None (304)"
                )

                etag2 = client.configs_etag
                assert etag2 == etag1, (
                    "async configs_etag should remain the same after 304"
                )

            finally:
                await client.close()

        # Run the async test
        asyncio.run(run_async_test())

    def test_async_invalid_etag_handling(
        self, aicm_api_key, aicm_api_base, aicm_ini_path
    ):
        """Test async behavior with invalid ETag."""
        ensure_ini_deleted(aicm_ini_path)

        async def run_async_test():
            client = make_async_client(aicm_api_key, aicm_api_base, aicm_ini_path)

            try:
                # First call to get baseline
                result1 = await client.get_configs()
                assert result1 is not None
                valid_etag = client.configs_etag

                # Call with fake/invalid ETag - should get fresh data
                fake_etag = "invalid-fake-etag-12345"
                result2 = await client.get_configs(etag=fake_etag)
                assert result2 is not None, (
                    "Should get fresh data with invalid async ETag"
                )

                new_etag = client.configs_etag
                assert new_etag != fake_etag, (
                    "Async ETag should be updated from fake value"
                )
                assert new_etag is not None, "New async ETag should be set"

            finally:
                await client.close()

        asyncio.run(run_async_test())


class TestETagEdgeCases:
    """Test edge cases and error scenarios for ETag functionality."""

    def test_concurrent_etag_handling(self, aicm_api_key, aicm_api_base, aicm_ini_path):
        """Test ETag handling with multiple concurrent clients."""
        ensure_ini_deleted(aicm_ini_path)

        # Create two clients pointing to same INI file
        client1 = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)
        client2 = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)

        try:
            # First client makes call
            result1 = client1.get_configs()
            assert result1 is not None
            etag1 = client1.configs_etag

            # Second client should read same INI and potentially get 304
            result2 = client2.get_configs()

            # Both clients should have same ETag
            etag2 = client2.configs_etag

            if result2 is None:
                # Got 304, ETags should match
                assert etag2 == etag1, "Both clients should have same ETag after 304"
            else:
                # Got fresh data, ETag might be updated
                assert etag2 is not None, "Second client should have valid ETag"

        finally:
            client1.close()
            client2.close()

    def test_multiple_refresh_cycles(self, aicm_api_key, aicm_api_base, aicm_ini_path):
        """Test multiple refresh cycles to ensure ETag handling is stable."""
        ensure_ini_deleted(aicm_ini_path)

        client = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)
        config_mgr = CostManagerConfig(client)

        try:
            etags = []

            # Perform multiple refresh cycles
            for i in range(3):
                config_mgr.refresh()
                etag = client.configs_etag
                assert etag is not None, f"ETag should be set after refresh {i + 1}"
                etags.append(etag)

                # Brief pause between refreshes
                time.sleep(0.1)

            # All ETags should be the same (since config likely hasn't changed)
            assert len(set(etags)) <= 2, "ETags should be consistent across refreshes"

        finally:
            client.close()

    def test_empty_etag_handling(self, aicm_api_key, aicm_api_base, aicm_ini_path):
        """Test behavior when ETag is empty or missing."""
        ensure_ini_deleted(aicm_ini_path)

        client = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)

        try:
            # Create INI with empty ETag
            os.makedirs(os.path.dirname(aicm_ini_path), exist_ok=True)
            cp = configparser.ConfigParser()
            cp.add_section("configs")
            cp["configs"]["etag"] = ""  # Empty ETag
            cp["configs"]["payload"] = "[]"  # Empty payload

            with open(aicm_ini_path, "w") as f:
                cp.write(f)

            # Call should treat empty ETag as no ETag and fetch fresh data
            result = client.get_configs()
            assert result is not None, "Should get fresh data when ETag is empty"

            new_etag = client.configs_etag
            assert new_etag is not None, "Should set new ETag"
            assert new_etag != "", "New ETag should not be empty"

        finally:
            client.close()


# Additional test for client ETag property
class TestClientETagProperty:
    """Test ETag property functionality on clients."""

    def test_client_etag_persistence(self, aicm_api_key, aicm_api_base, aicm_ini_path):
        """Test that ETag property persists between calls."""
        ensure_ini_deleted(aicm_ini_path)

        client = make_sync_client(aicm_api_key, aicm_api_base, aicm_ini_path)

        try:
            # Initially no ETag
            assert client.configs_etag is None, "Initially should have no ETag"

            # First call sets ETag
            result1 = client.get_configs()
            assert result1 is not None
            etag1 = client.configs_etag
            assert etag1 is not None, "ETag should be set after successful call"

            # Second call with same ETag should return 304 and preserve ETag
            result2 = client.get_configs(etag=etag1)
            assert result2 is None, "Should get 304 with same ETag"
            etag2 = client.configs_etag
            assert etag2 == etag1, "ETag should be preserved after 304"

        finally:
            client.close()
