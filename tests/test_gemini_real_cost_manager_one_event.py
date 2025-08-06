#!/usr/bin/env python3
"""
Standalone test for Gemini cost tracking that sends exactly one event to the server.
This is for debugging delivery issues - should create one payload and deliver one event.
"""

import json
import os
import time

import pytest
import requests

# Import Gemini dependencies
genai = pytest.importorskip("google.genai")
from google.genai import types

from aicostmanager import CostManager


def verify_event_delivered(
    aicm_api_key, aicm_api_base, response_id, timeout=10, max_attempts=8
):
    """Verify that a usage event was successfully delivered and check /track-usage status codes."""
    headers = {
        "Authorization": f"Bearer {aicm_api_key}",
        "Content-Type": "application/json",
    }

    print(f"🔍 Looking for event with response_id: {response_id}")

    for attempt in range(max_attempts):
        try:
            events_response = requests.get(
                f"{aicm_api_base}/api/v1/usage/events/",
                headers=headers,
                params={"limit": 20},
                timeout=timeout,
            )

            print(
                f"  Attempt {attempt + 1}: GET /api/v1/usage/events/ -> {events_response.status_code}"
            )

            assert events_response.status_code == 200, (
                f"Failed to fetch events: {events_response.status_code} - {events_response.text}"
            )

            events_data = events_response.json()
            results = events_data.get("results", [])
            print(f"  Found {len(results)} total events on server")

            for i, event in enumerate(results):
                event_response_id = event.get("response_id")
                print(f"    Event {i + 1}: response_id={event_response_id}")

                if event_response_id == response_id:
                    print("  ✅ Found matching event!")

                    # Validate required fields are present
                    required_fields = [
                        "event_id",
                        "config_id",
                        "timestamp",
                        "response_id",
                        "usage",
                    ]
                    for field in required_fields:
                        assert field in event, (
                            f"Required field '{field}' missing from event: {event}"
                        )

                    # Check for forbidden fields
                    forbidden_fields = ["provider"]
                    for field in forbidden_fields:
                        assert field not in event, (
                            f"Forbidden field '{field}' found in event: {event}"
                        )

                    return event

            print("  Event not found yet, waiting 3s...")
            if attempt < max_attempts - 1:
                time.sleep(3)

        except Exception as e:
            print(f"  Error on attempt {attempt + 1}: {e}")
            if attempt < max_attempts - 1:
                time.sleep(3)
            else:
                raise e

    print(f"❌ Event with response_id {response_id} was never delivered")
    return None


def verify_track_usage_success(client, payload_data):
    """Directly test /track-usage endpoint to ensure 20x status codes."""
    try:
        test_payload = {"usage_records": [payload_data]}

        # Validate payload structure
        required_fields = [
            "config_id",
            "service_id",
            "timestamp",
            "response_id",
            "usage",
        ]
        for field in required_fields:
            assert field in payload_data, (
                f"Required field '{field}' missing from payload: {payload_data}"
            )

        forbidden_fields = ["provider"]
        for field in forbidden_fields:
            assert field not in payload_data, (
                f"Forbidden field '{field}' found in payload: {payload_data}"
            )

        result = client.track_usage(test_payload)
        assert result is not None
        print(f"✅ /track-usage call successful: {result}")
        return True

    except Exception as e:
        print(f"❌ /track-usage call failed: {e}")
        print(f"❌ Failed payload: {json.dumps(payload_data, indent=2, default=str)}")
        raise e


class Gemini:
    """Wrapper for Google GenAI client to provide proper API ID detection."""

    __module__ = "google.genai.client"

    def __init__(self, api_key):
        self._client = genai.Client(api_key=api_key)

    def __getattr__(self, name):
        """Proxy all attributes to the underlying client."""
        return getattr(self._client, name)


def _make_client(api_key):
    """Create Google GenAI client with proper naming."""
    return Gemini(api_key)


def test_gemini_single_event_delivery():
    """Test that makes exactly one Gemini API call and verifies one event is delivered."""

    # Environment setup
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    aicm_api_key = os.environ.get("AICM_API_KEY")
    aicm_api_base = os.environ.get("AICM_API_BASE", "http://127.0.0.1:8001")
    aicm_ini_path = os.environ.get("AICM_INI_PATH", "/tmp/test_aicm.ini")

    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in environment")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in environment")

    print(f"🔧 Using AICM API Base: {aicm_api_base}")
    print(f"🔧 Using AICM INI Path: {aicm_ini_path}")

    # Create Gemini client
    client = _make_client(google_api_key)
    print(f"✅ Created Gemini client: {type(client)}")

    # Create tracked client
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
        client_customer_key="test_single_event",
        context={"test": "single_event"},
    )

    print("✅ Created CostManager")
    print(f"   API ID: {tracked_client.api_id}")
    print(f"   Configs found: {len(tracked_client.configs)}")

    for i, config in enumerate(tracked_client.configs):
        print(
            f"   Config {i + 1}: api_id={config.api_id}, config_id={config.config_id}"
        )

    # Refresh config to pick up server changes
    tracked_client.config_manager.refresh()

    # Check initial state
    initial_payloads = tracked_client.get_tracked_payloads()
    print(f"📊 Initial payloads: {len(initial_payloads)}")

    # Make ONE API call
    print("\n🚀 Making single Gemini API call...")
    response = tracked_client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents="Tell me a very short dad joke in one sentence.",
        config=types.GenerateContentConfig(temperature=0.1),
    )

    print("✅ API call completed")
    print(f"   Response type: {type(response)}")
    if hasattr(response, "text"):
        print(f"   Response text: {response.text[:100]}...")

    # Check payloads after call
    final_payloads = tracked_client.get_tracked_payloads()
    print(f"📊 Final payloads: {len(final_payloads)}")

    # Verify exactly one payload was generated
    assert len(final_payloads) == 1, (
        f"Expected exactly 1 payload, got {len(final_payloads)}"
    )
    payload = final_payloads[0]

    print("\n📦 Generated payload:")
    for key, value in payload.items():
        if isinstance(value, dict):
            print(f"   {key}: {type(value)} with {len(value)} keys")
        else:
            print(f"   {key}: {value}")

    print("\n📦 FULL PAYLOAD JSON:")
    print(json.dumps(payload, indent=2, default=str))

    # Test direct /track-usage call
    print("\n🧪 Testing direct /track-usage call...")
    verify_track_usage_success(tracked_client.cm_client, payload)

    # Extract response_id
    response_id = payload.get("response_id")
    print(f"\n🔍 Response ID from payload: {response_id}")

    if not response_id:
        # Try alternative extraction methods
        print("⚠️  No response_id in payload, trying alternative extraction...")
        if hasattr(response, "candidates") and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, "citation_metadata"):
                    response_id = getattr(
                        candidate.citation_metadata, "citation_sources", [{}]
                    )[0].get("uri")
                break

    # Wait a moment for delivery processing
    print("\n⏳ Waiting 3 seconds for delivery processing...")
    time.sleep(3)

    # Verify event was delivered to server
    if response_id:
        print("\n🔍 Verifying event delivery...")
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)

        if event:
            print("✅ Event successfully delivered and verified!")
            print(f"   Event ID: {event.get('event_id')}")
            print(f"   Config ID: {event.get('config_id')}")
            print(f"   Client customer key: {event.get('client_customer_key')}")
            print(f"   Context: {event.get('context')}")

            # Verify test-specific fields
            assert event.get("client_customer_key") == "test_single_event"
            assert event.get("context", {}).get("test") == "single_event"
            assert "usage" in event
        else:
            print("❌ Event verification failed - event not found on server")
            pytest.fail(
                f"Usage event for response_id {response_id} was not delivered to server"
            )
    else:
        print("⚠️  No response_id available - cannot verify server delivery")
        print("   This might indicate a payload generation issue")


if __name__ == "__main__":
    # Set up environment for standalone execution
    import sys

    # Add project root to path
    sys.path.insert(
        0, "/Users/keytonweissinger/home/aicostmanager/aicostmanager-python"
    )

    # Set default environment if not already set
    if not os.environ.get("AICM_API_KEY"):
        os.environ["AICM_API_KEY"] = (
            "sk-api01-361e196e-de00-4be4-94cc-88dc1a4bffc4.7dbb634f-00f3-4506-9979-559dd22807d0"
        )
    if not os.environ.get("AICM_API_BASE"):
        os.environ["AICM_API_BASE"] = "http://127.0.0.1:8001"
    if not os.environ.get("AICM_INI_PATH"):
        os.environ["AICM_INI_PATH"] = "/Users/keytonweissinger/home/AICM.INI"

    # Run the test
    test_gemini_single_event_delivery()
    print("\n🎉 Test completed successfully!")
