import json
import time

import pytest
import requests

genai = pytest.importorskip("google.genai")
from google.genai import types

from aicostmanager import CostManager, UniversalExtractor


def verify_event_delivered(
    aicm_api_key, aicm_api_base, response_id, timeout=10, max_attempts=8
):
    """Verify that a usage event was successfully delivered and check /track-usage status codes."""
    headers = {
        "Authorization": f"Bearer {aicm_api_key}",
        "Content-Type": "application/json",
    }
    for attempt in range(max_attempts):
        try:
            events_response = requests.get(
                f"{aicm_api_base}/api/v1/usage/events/",
                headers=headers,
                params={"limit": 20},
                timeout=timeout,
            )
            assert events_response.status_code == 200, (
                f"Failed to fetch events: {events_response.status_code} - {events_response.text}"
            )

            events_data = events_response.json()
            results = events_data.get("results", [])
            for event in results:
                if event.get("response_id") == response_id:
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
                    forbidden_fields = ["provider"]
                    for field in forbidden_fields:
                        assert field not in event, (
                            f"Forbidden field '{field}' found in event: {event}"
                        )
                    return event
            if attempt < max_attempts - 1:
                time.sleep(3)
        except Exception:
            if attempt < max_attempts - 1:
                time.sleep(3)
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


def test_gemini_cost_manager_configs(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test that Gemini configs are available."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_client(google_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    gem_configs = [c for c in configs if c.api_id == "google.genai.client"]
    assert gem_configs


def test_gemini_config_retrieval_and_extractor_interaction(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test config retrieval and extractor setup."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_client(google_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    gem_configs = [cfg for cfg in configs if cfg.api_id == "google.genai.client"]
    assert gem_configs
    extractor = UniversalExtractor(gem_configs)
    for config in gem_configs:
        handling = config.handling_config
        assert isinstance(handling, dict)
        assert "tracked_methods" in handling
        assert "request_fields" in handling
        assert "response_fields" in handling
        assert "payload_mapping" in handling


def test_gemini_generate_content_with_dad_joke(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test non-streaming Gemini generate_content call."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")

    client = _make_client(google_api_key)
    tracked_client = CostManager(client)

    response = tracked_client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents="Tell me a dad joke.",
        config=types.GenerateContentConfig(temperature=0.7),
    )

    assert response is not None
    assert hasattr(response, "text")
    assert response.text.strip()


def test_gemini_generate_content_streaming_with_dad_joke(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test streaming Gemini generate_content_stream call."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")

    client = _make_client(google_api_key)
    tracked_client = CostManager(client)

    stream = tracked_client.models.generate_content_stream(
        model="gemini-2.0-flash-lite",
        contents="Tell me a dad joke.",
        config=types.GenerateContentConfig(temperature=0.7),
    )

    full_content = ""
    chunk_count = 0

    for chunk in stream:
        chunk_count += 1
        if hasattr(chunk, "text") and chunk.text:
            full_content += chunk.text

    assert chunk_count > 0
    assert full_content.strip()


def test_gemini_generate_content_usage_delivery(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that non-streaming generate_content automatically delivers usage payload with proper validation."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    client = _make_client(google_api_key)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )

    # Refresh config to pick up server changes
    tracked_client.config_manager.refresh()

    response = tracked_client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents="Tell me a dad joke.",
        config=types.GenerateContentConfig(temperature=0.7),
    )

    assert response is not None
    assert hasattr(response, "text")
    assert response.text.strip()

    # Test payload structure and /track-usage call success
    payloads = tracked_client.get_tracked_payloads()
    if len(payloads) > 0:
        verify_track_usage_success(tracked_client.cm_client, payloads[0])

    # Wait for delivery and verify event
    time.sleep(5)

    # Extract response_id from the response
    response_id = None
    if hasattr(response, "candidates") and response.candidates:
        # Try to get response_id from candidates
        for candidate in response.candidates:
            if hasattr(candidate, "citation_metadata"):
                response_id = getattr(
                    candidate.citation_metadata, "citation_sources", [{}]
                )[0].get("uri")
            break

    # Fallback to checking payloads for generated response_id
    if not response_id and len(payloads) > 0:
        response_id = payloads[0].get("response_id")

    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None, (
            f"Usage event {response_id} was not delivered to server"
        )
        assert "usage" in event


def test_gemini_generate_content_streaming_usage_delivery(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that streaming generate_content_stream automatically delivers usage payload with proper validation."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    client = _make_client(google_api_key)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )

    # Refresh config to pick up server changes
    tracked_client.config_manager.refresh()

    stream = tracked_client.models.generate_content_stream(
        model="gemini-2.0-flash-lite",
        contents="Tell me a dad joke.",
        config=types.GenerateContentConfig(temperature=0.7),
    )

    response_id = None
    full_content = ""
    chunk_count = 0

    for chunk in stream:
        chunk_count += 1
        if hasattr(chunk, "text") and chunk.text:
            full_content += chunk.text
        # Try to extract response_id from chunks
        if hasattr(chunk, "candidates") and chunk.candidates:
            for candidate in chunk.candidates:
                if hasattr(candidate, "citation_metadata"):
                    response_id = getattr(
                        candidate.citation_metadata, "citation_sources", [{}]
                    )[0].get("uri")
                break

    assert chunk_count > 0
    assert full_content.strip()

    # Test payload structure and /track-usage call success
    payloads = tracked_client.get_tracked_payloads()
    if len(payloads) > 0:
        verify_track_usage_success(tracked_client.cm_client, payloads[0])
        # Use generated response_id from payload if not found in response
        if not response_id:
            response_id = payloads[0].get("response_id")

    # Wait for delivery and verify event
    time.sleep(5)

    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None, (
            f"Streaming usage event {response_id} was not delivered to server"
        )
        assert "usage" in event


def test_extractor_payload_generation(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test extractor payload generation."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")

    client = _make_client(google_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    gem_configs = [cfg for cfg in configs if cfg.api_id == "google.genai.client"]
    extractor = UniversalExtractor(gem_configs)

    response = tracked_client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents="Tell me a dad joke.",
        config=types.GenerateContentConfig(temperature=0.7),
    )

    for config in gem_configs:
        tracking_data = extractor._build_tracking_data(
            config,
            "models.generate_content",
            (),
            {
                "model": "gemini-2.0-flash-lite",
                "contents": "Tell me a dad joke.",
                "config": types.GenerateContentConfig(temperature=0.7),
            },
            response,
            client,
        )
        assert "timestamp" in tracking_data
        assert "method" in tracking_data
        assert "config_identifier" in tracking_data
        assert "request_data" in tracking_data
        assert "response_data" in tracking_data
        assert "client_data" in tracking_data

        # Test payload generation with validation
        payload_data = extractor._build_payload(config, tracking_data)
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
