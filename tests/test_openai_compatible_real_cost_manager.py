import json
import time

import pytest
import requests

openai = pytest.importorskip("openai")
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


def _make_deepseek_client(api_key):
    """Create DeepSeek client using OpenAI API format."""
    return openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")


def _make_gemini_openai_client(api_key):
    """Create Gemini client using OpenAI API format."""
    return openai.OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )


# DeepSeek Tests
def test_deepseek_openai_cost_manager_configs(
    deepseek_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test that DeepSeek OpenAI configs are available."""
    if not deepseek_api_key:
        pytest.skip("DEEPSEEK_API_KEY not set in .env file")
    client = _make_deepseek_client(deepseek_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    # Should use openai configs since it's OpenAI API compatible
    openai_configs = [c for c in configs if c.api_id == "openai"]
    assert openai_configs


def test_deepseek_openai_config_retrieval_and_extractor_interaction(
    deepseek_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test DeepSeek config retrieval and extractor setup."""
    if not deepseek_api_key:
        pytest.skip("DEEPSEEK_API_KEY not set in .env file")
    client = _make_deepseek_client(deepseek_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    deepseek_configs = [cfg for cfg in configs if cfg.api_id == "openai"]
    assert deepseek_configs
    extractor = UniversalExtractor(deepseek_configs)
    for config in deepseek_configs:
        handling = config.handling_config
        assert isinstance(handling, dict)
        assert "tracked_methods" in handling
        assert "request_fields" in handling
        assert "response_fields" in handling
        assert "payload_mapping" in handling


def test_deepseek_openai_chat_completion_with_dad_joke(
    deepseek_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test non-streaming DeepSeek chat completion call."""
    if not deepseek_api_key:
        pytest.skip("DEEPSEEK_API_KEY not set in .env file")

    client = _make_deepseek_client(deepseek_api_key)
    tracked_client = CostManager(client)

    response = tracked_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        temperature=0.7,
        max_tokens=100,
    )

    assert response is not None
    assert hasattr(response, "choices")
    assert len(response.choices) > 0
    assert response.choices[0].message.content.strip()


def test_deepseek_openai_chat_completion_streaming_with_dad_joke(
    deepseek_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test streaming DeepSeek chat completion call."""
    if not deepseek_api_key:
        pytest.skip("DEEPSEEK_API_KEY not set in .env file")

    client = _make_deepseek_client(deepseek_api_key)
    tracked_client = CostManager(client)

    stream = tracked_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        temperature=0.7,
        max_tokens=100,
        stream=True,
    )

    full_content = ""
    chunk_count = 0

    for chunk in stream:
        chunk_count += 1
        if chunk.choices and chunk.choices[0].delta.content:
            full_content += chunk.choices[0].delta.content

    assert chunk_count > 0
    assert full_content.strip()


def test_deepseek_openai_chat_completion_usage_delivery(
    deepseek_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that non-streaming DeepSeek chat completion automatically delivers usage payload with proper validation."""
    if not deepseek_api_key:
        pytest.skip("DEEPSEEK_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    client = _make_deepseek_client(deepseek_api_key)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
        client_customer_key="test_client",
        context={"foo": "bar"},
    )

    # Refresh config to pick up server changes
    tracked_client.config_manager.refresh()

    response = tracked_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        temperature=0.7,
        max_tokens=100,
    )

    assert response is not None
    assert hasattr(response, "choices")
    assert len(response.choices) > 0
    assert response.choices[0].message.content.strip()

    # Test payload structure and /track-usage call success
    payloads = tracked_client.get_tracked_payloads()
    if len(payloads) > 0:
        verify_track_usage_success(tracked_client.cm_client, payloads[0])

    # Wait for delivery and verify event
    time.sleep(5)

    # Get response_id from the payload (should be generated UUID or from response)
    response_id = None
    if hasattr(response, "id"):
        response_id = response.id
    elif len(payloads) > 0:
        response_id = payloads[0].get("response_id")

    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None, (
            f"Usage event {response_id} was not delivered to server"
        )
        assert event.get("client_customer_key") == "test_client"
        assert event.get("context", {}).get("foo") == "bar"
        assert "usage" in event


def test_deepseek_openai_chat_completion_streaming_usage_delivery(
    deepseek_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that streaming DeepSeek chat completion automatically delivers usage payload with proper validation."""
    if not deepseek_api_key:
        pytest.skip("DEEPSEEK_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    client = _make_deepseek_client(deepseek_api_key)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
        client_customer_key="test_client",
        context={"foo": "bar"},
    )

    # Refresh config to pick up server changes
    tracked_client.config_manager.refresh()

    stream = tracked_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        temperature=0.7,
        max_tokens=100,
        stream=True,
    )

    response_id = None
    full_content = ""
    chunk_count = 0

    for chunk in stream:
        chunk_count += 1
        if chunk.choices and chunk.choices[0].delta.content:
            full_content += chunk.choices[0].delta.content
        # Try to extract response_id from chunks
        if hasattr(chunk, "id"):
            response_id = chunk.id

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
        assert event.get("client_customer_key") == "test_client"
        assert event.get("context", {}).get("foo") == "bar"
        assert "usage" in event


# Gemini OpenAI Tests
def test_gemini_openai_cost_manager_configs(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test that Gemini OpenAI configs are available."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_gemini_openai_client(google_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    # Should use openai configs since it's OpenAI API compatible
    gemini_configs = [c for c in configs if c.api_id == "openai"]
    assert gemini_configs


def test_gemini_openai_config_retrieval_and_extractor_interaction(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test Gemini OpenAI config retrieval and extractor setup."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_gemini_openai_client(google_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    gemini_configs = [cfg for cfg in configs if cfg.api_id == "openai"]
    assert gemini_configs
    extractor = UniversalExtractor(gemini_configs)
    for config in gemini_configs:
        handling = config.handling_config
        assert isinstance(handling, dict)
        assert "tracked_methods" in handling
        assert "request_fields" in handling
        assert "response_fields" in handling
        assert "payload_mapping" in handling


def test_gemini_openai_chat_completion_with_dad_joke(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test non-streaming Gemini OpenAI chat completion call."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")

    client = _make_gemini_openai_client(google_api_key)
    tracked_client = CostManager(client)

    response = tracked_client.chat.completions.create(
        model="gemini-2.0-flash-lite",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        temperature=0.7,
        max_tokens=100,
    )

    assert response is not None
    assert hasattr(response, "choices")
    assert len(response.choices) > 0
    assert response.choices[0].message.content.strip()


def test_gemini_openai_chat_completion_streaming_with_dad_joke(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test streaming Gemini OpenAI chat completion call."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")

    client = _make_gemini_openai_client(google_api_key)
    tracked_client = CostManager(client)

    stream = tracked_client.chat.completions.create(
        model="gemini-2.0-flash-lite",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        temperature=0.7,
        max_tokens=100,
        stream=True,
    )

    full_content = ""
    chunk_count = 0

    for chunk in stream:
        chunk_count += 1
        if chunk.choices and chunk.choices[0].delta.content:
            full_content += chunk.choices[0].delta.content

    assert chunk_count > 0
    assert full_content.strip()


def test_gemini_openai_chat_completion_usage_delivery(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that non-streaming Gemini OpenAI chat completion automatically delivers usage payload with proper validation."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    client = _make_gemini_openai_client(google_api_key)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
        client_customer_key="test_client",
        context={"foo": "bar"},
    )

    # Refresh config to pick up server changes
    tracked_client.config_manager.refresh()

    response = tracked_client.chat.completions.create(
        model="gemini-2.0-flash-lite",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        temperature=0.7,
        max_tokens=100,
    )

    assert response is not None
    assert hasattr(response, "choices")
    assert len(response.choices) > 0
    assert response.choices[0].message.content.strip()

    # Test payload structure and /track-usage call success
    payloads = tracked_client.get_tracked_payloads()
    if len(payloads) > 0:
        verify_track_usage_success(tracked_client.cm_client, payloads[0])

    # Wait for delivery and verify event
    time.sleep(5)

    # Get response_id from the payload (should be generated UUID or from response)
    response_id = None
    if hasattr(response, "id"):
        response_id = response.id
    elif len(payloads) > 0:
        response_id = payloads[0].get("response_id")

    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None, (
            f"Usage event {response_id} was not delivered to server"
        )
        assert event.get("client_customer_key") == "test_client"
        assert event.get("context", {}).get("foo") == "bar"
        assert "usage" in event


def test_gemini_openai_chat_completion_streaming_usage_delivery(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that streaming Gemini OpenAI chat completion automatically delivers usage payload with proper validation."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    client = _make_gemini_openai_client(google_api_key)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
        client_customer_key="test_client",
        context={"foo": "bar"},
    )

    # Refresh config to pick up server changes
    tracked_client.config_manager.refresh()

    stream = tracked_client.chat.completions.create(
        model="gemini-2.0-flash-lite",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        temperature=0.7,
        max_tokens=100,
        stream=True,
    )

    response_id = None
    full_content = ""
    chunk_count = 0

    for chunk in stream:
        chunk_count += 1
        if chunk.choices and chunk.choices[0].delta.content:
            full_content += chunk.choices[0].delta.content
        # Try to extract response_id from chunks
        if hasattr(chunk, "id"):
            response_id = chunk.id

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
        assert event.get("client_customer_key") == "test_client"
        assert event.get("context", {}).get("foo") == "bar"
        assert "usage" in event


def test_deepseek_extractor_payload_generation(
    deepseek_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test DeepSeek extractor payload generation."""
    if not deepseek_api_key:
        pytest.skip("DEEPSEEK_API_KEY not set in .env file")

    client = _make_deepseek_client(deepseek_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    deepseek_configs = [cfg for cfg in configs if cfg.api_id == "openai"]
    extractor = UniversalExtractor(deepseek_configs)

    response = tracked_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        temperature=0.7,
        max_tokens=100,
    )

    for config in deepseek_configs:
        tracking_data = extractor._build_tracking_data(
            config,
            "chat.completions.create",
            (),
            {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "Tell me a dad joke."}],
                "temperature": 0.7,
                "max_tokens": 100,
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


def test_gemini_openai_extractor_payload_generation(
    google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test Gemini OpenAI extractor payload generation."""
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")

    client = _make_gemini_openai_client(google_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    gemini_configs = [cfg for cfg in configs if cfg.api_id == "openai"]
    extractor = UniversalExtractor(gemini_configs)

    response = tracked_client.chat.completions.create(
        model="gemini-2.0-flash-lite",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        temperature=0.7,
        max_tokens=100,
    )

    for config in gemini_configs:
        tracking_data = extractor._build_tracking_data(
            config,
            "chat.completions.create",
            (),
            {
                "model": "gemini-2.0-flash-lite",
                "messages": [{"role": "user", "content": "Tell me a dad joke."}],
                "temperature": 0.7,
                "max_tokens": 100,
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
