import json
import time

import pytest
import requests

openai = pytest.importorskip("openai")
from aicostmanager import CostManager, UniversalExtractor


def verify_event_delivered(
    aicm_api_key, aicm_api_base, response_id, timeout=10, max_attempts=8
):
    """
    Verify that a usage event with the given response_id was delivered to the server.

    Args:
        aicm_api_key: API key for authentication
        aicm_api_base: Base URL for the API
        response_id: The response_id to search for
        timeout: Request timeout in seconds
        max_attempts: Maximum number of attempts with delay between each

    Returns:
        dict: The event data if found, None if not found
    """
    headers = {
        "Authorization": f"Bearer {aicm_api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(max_attempts):
        try:
            # Query events - if response_id filtering doesn't work, get recent events and search
            events_response = requests.get(
                f"{aicm_api_base}/api/v1/usage/events/",
                headers=headers,
                params={"limit": 20},  # Get more events to search through
                timeout=timeout,
            )

            if events_response.status_code == 200:
                events_data = events_response.json()
                results = events_data.get("results", [])

                # Search for our specific response_id in the results
                for event in results:
                    if event.get("response_id") == response_id:
                        print(f"✅ Found usage event for response_id: {response_id}")
                        print(f"   Event data: {json.dumps(event, indent=2)}")
                        return event

            # Wait before next attempt (except on last attempt)
            if attempt < max_attempts - 1:
                time.sleep(3)
                print(
                    f"⏱️  Attempt {attempt + 1}/{max_attempts}: Event not found yet, waiting..."
                )

        except Exception as e:
            print(f"⚠️  Error checking usage events (attempt {attempt + 1}): {e}")
            if attempt < max_attempts - 1:
                time.sleep(3)

    print(
        f"❌ Usage event for response_id {response_id} not found after {max_attempts} attempts"
    )
    return None


def test_openai_cost_manager_configs(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")
    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(openai_client)
    configs = tracked_client.configs
    print("Loaded configs:", configs)
    openai_configs = [cfg for cfg in configs if cfg.api_id == "openai"]
    assert len(openai_configs) == 2, (
        f"Expected 2 openai configs, got {len(openai_configs)}"
    )


def test_openai_config_retrieval_and_extractor_interaction(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test retrieving appropriate Config and UniversalExtractor interaction types."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(openai_client)

    # Retrieve the appropriate Config for the wrapped OpenAI client
    configs = tracked_client.configs
    openai_configs = [cfg for cfg in configs if cfg.api_id == "openai"]
    assert len(openai_configs) > 0, "No OpenAI configs found"

    # Test interaction types with UniversalExtractor based on handling_config
    extractor = UniversalExtractor(openai_configs)

    # Check that each config has the expected handling_config structure
    for config in openai_configs:
        assert hasattr(config, "handling_config"), (
            f"Config {config.config_id} missing handling_config"
        )
        assert isinstance(config.handling_config, dict), (
            f"Config {config.config_id} handling_config is not a dict"
        )

        # Check for required handling_config fields
        handling_config = config.handling_config
        print(f"Config {config.config_id} handling_config: {handling_config}")

        # Verify tracked_methods exist
        assert "tracked_methods" in handling_config, (
            f"Config {config.config_id} missing tracked_methods"
        )
        tracked_methods = handling_config["tracked_methods"]
        assert isinstance(tracked_methods, list), (
            f"Config {config.config_id} tracked_methods is not a list"
        )

        # Verify request_fields exist
        assert "request_fields" in handling_config, (
            f"Config {config.config_id} missing request_fields"
        )
        request_fields = handling_config["request_fields"]
        assert isinstance(request_fields, list), (
            f"Config {config.config_id} request_fields is not a list"
        )

        # Verify response_fields exist
        assert "response_fields" in handling_config, (
            f"Config {config.config_id} missing response_fields"
        )
        response_fields = handling_config["response_fields"]
        assert isinstance(response_fields, list), (
            f"Config {config.config_id} response_fields is not a list"
        )

        # Verify payload_mapping exists
        assert "payload_mapping" in handling_config, (
            f"Config {config.config_id} missing payload_mapping"
        )
        payload_mapping = handling_config["payload_mapping"]
        assert isinstance(payload_mapping, dict), (
            f"Config {config.config_id} payload_mapping is not a dict"
        )


def test_openai_chat_completion_with_dad_joke(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test OpenAI chat completion API with dad joke prompt."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(openai_client)

    # Test chat completion API
    try:
        response = tracked_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Tell me a dad joke."}],
            max_tokens=100,
        )

        print(f"Chat completion response: {response}")
        assert response is not None
        assert hasattr(response, "choices")
        assert len(response.choices) > 0

        # Verify the response contains content
        choice = response.choices[0]
        assert hasattr(choice, "message")
        assert hasattr(choice.message, "content")
        assert choice.message.content is not None

        print(f"Dad joke response: {choice.message.content}")

    except Exception as e:
        pytest.fail(f"Chat completion API call failed: {e}")


def test_openai_chat_completion_streaming_with_dad_joke(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test OpenAI chat completion API with streaming enabled."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(openai_client)

    # Test streaming chat completion API
    try:
        stream = tracked_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Tell me a dad joke."}],
            max_tokens=100,
            stream=True,
        )

        print("Streaming chat completion response:")
        full_content = ""
        chunk_count = 0

        for chunk in stream:
            chunk_count += 1

            # Handle content chunks - check if choices exist and have delta content
            if (
                hasattr(chunk, "choices")
                and len(chunk.choices) > 0
                and hasattr(chunk.choices[0], "delta")
                and chunk.choices[0].delta.content is not None
            ):
                content = chunk.choices[0].delta.content
                full_content += content
                print(f"Chunk {chunk_count}: {content}")

            # Handle usage chunk - check if this is the final usage chunk
            if hasattr(chunk, "usage") and chunk.usage is not None:
                print(f"Usage chunk {chunk_count}: {chunk.usage}")

        print(f"Full streaming response: {full_content}")
        assert chunk_count > 0, "No chunks received in streaming response"
        assert full_content.strip(), "No content received in streaming response"

    except Exception as e:
        pytest.fail(f"Streaming chat completion API call failed: {e}")


def test_openai_completion_with_dad_joke(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test OpenAI completion API with dad joke prompt."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(openai_client)

    # Test completion API (legacy endpoint)
    try:
        response = tracked_client.completions.create(
            model="gpt-3.5-turbo-instruct", prompt="Tell me a dad joke.", max_tokens=100
        )

        print(f"Completion response: {response}")
        assert response is not None
        assert hasattr(response, "choices")
        assert len(response.choices) > 0

        # Verify the response contains content
        choice = response.choices[0]
        assert hasattr(choice, "text")
        assert choice.text is not None

        print(f"Dad joke completion response: {choice.text}")

    except Exception as e:
        pytest.fail(f"Completion API call failed: {e}")


def test_openai_completion_streaming_with_dad_joke(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test OpenAI completion API with streaming enabled."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(openai_client)

    # Test streaming completion API (legacy endpoint)
    try:
        stream = tracked_client.completions.create(
            model="gpt-3.5-turbo-instruct",
            prompt="Tell me a dad joke.",
            max_tokens=100,
            stream=True,
        )

        print("Streaming completion response:")
        full_content = ""
        chunk_count = 0

        for chunk in stream:
            chunk_count += 1

            # Handle content chunks - legacy completion streaming uses text directly
            if hasattr(chunk, "choices") and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                content = None

                # For legacy completion streaming (uses text directly)
                if hasattr(choice, "text") and choice.text is not None:
                    content = choice.text

                if content is not None:
                    full_content += content
                    print(f"Chunk {chunk_count}: {content}")

            # Handle usage chunk - check if this is the final usage chunk
            if hasattr(chunk, "usage") and chunk.usage is not None:
                print(f"Usage chunk {chunk_count}: {chunk.usage}")

        print(f"Full streaming completion response: {full_content}")
        assert chunk_count > 0, "No chunks received in streaming completion response"
        assert full_content.strip(), (
            "No content received in streaming completion response"
        )

    except Exception as e:
        pytest.fail(f"Streaming completion API call failed: {e}")


def test_openai_responses_api_with_dad_joke(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test OpenAI responses API with dad joke prompt."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(openai_client)

    # Test responses API (non-streaming)
    try:
        response = tracked_client.responses.create(
            model="gpt-3.5-turbo",
            input="Tell me a dad joke.",
        )

        print(f"Responses API response: {response}")
        assert response is not None
        assert hasattr(response, "output")
        assert len(response.output) > 0

        # Verify the response contains content
        output = response.output[0]
        assert hasattr(output, "content")
        assert len(output.content) > 0
        assert hasattr(output.content[0], "text")
        assert output.content[0].text is not None

        print(f"Dad joke responses API response: {output.content[0].text}")

    except Exception as e:
        pytest.fail(f"Responses API call failed: {e}")


def test_openai_responses_api_streaming_with_dad_joke(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test OpenAI responses API with streaming enabled."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(openai_client)

    # Test streaming responses API
    try:
        stream = tracked_client.responses.create(
            model="gpt-3.5-turbo",
            input="Tell me a dad joke.",
            stream=True,
        )

        print("Streaming responses API response:")
        full_content = ""
        chunk_count = 0

        for chunk in stream:
            chunk_count += 1

            # Handle ResponseTextDeltaEvent which contains the actual text content
            if hasattr(chunk, "type") and chunk.type == "response.output_text.delta":
                if hasattr(chunk, "delta") and chunk.delta:
                    content = chunk.delta
                    full_content += content
                    print(f"Chunk {chunk_count}: {content}")

            # Also check for the final completed response
            elif hasattr(chunk, "type") and chunk.type == "response.completed":
                if hasattr(chunk, "response") and hasattr(chunk.response, "output"):
                    for output in chunk.response.output:
                        if hasattr(output, "content"):
                            for content_part in output.content:
                                if hasattr(content_part, "text") and content_part.text:
                                    print(f"Final response text: {content_part.text}")

        print(f"Full streaming responses API response: {full_content}")
        assert chunk_count > 0, "No chunks received in streaming responses API response"
        assert full_content.strip(), (
            "No content received in streaming responses API response"
        )

    except Exception as e:
        pytest.fail(f"Streaming responses API call failed: {e}")


def test_extractor_payload_generation(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test that UniversalExtractor generates payloads from API calls."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(openai_client)

    # Get configs and create extractor
    configs = tracked_client.configs
    openai_configs = [cfg for cfg in configs if cfg.api_id == "openai"]
    extractor = UniversalExtractor(openai_configs)

    # Make a test API call
    try:
        response = tracked_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Tell me a dad joke."}],
            max_tokens=50,
        )

        # Test that the extractor can process the call
        # Note: We can't directly test the extractor's process_call method
        # since it's called internally by CostManager, but we can verify
        # that the response structure is compatible with the extractor

        for config in openai_configs:
            # Test that the extractor can handle the response structure
            tracking_data = extractor._build_tracking_data(
                config,
                "chat.completions.create",
                (),
                {
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "system", "content": "Tell me a dad joke."}],
                    "max_tokens": 50,
                },
                response,
                openai_client,
            )

            assert "timestamp" in tracking_data
            assert "method" in tracking_data
            assert "config_identifier" in tracking_data
            assert "request_data" in tracking_data
            assert "response_data" in tracking_data
            assert "client_data" in tracking_data
            assert "usage_data" in tracking_data

            print(
                f"Generated tracking data for config {config.config_id}: {tracking_data}"
            )

    except Exception as e:
        pytest.fail(f"Extractor payload generation test failed: {e}")


def test_openai_chat_completion_usage_delivery(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that OpenAI chat completion automatically delivers usage payload to /track-usage."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(
        openai_client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )

    # Make a test API call that should trigger automatic usage delivery
    try:
        response = tracked_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Tell me a dad joke."}],
            max_tokens=50,
        )

        print(f"Chat completion response: {response}")
        assert response is not None
        assert hasattr(response, "choices")
        assert len(response.choices) > 0

        # Verify that the usage event was delivered to the server
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response.id)
        assert event is not None, (
            f"Usage event for response_id {response.id} was not delivered to server"
        )

        # Verify event structure
        assert event.get("config_id") == "openai_chat"
        assert event.get("service_id") == response.model
        assert event.get("response_id") == response.id
        assert "usage" in event
        assert "timestamp" in event

        print(f"Dad joke response: {response.choices[0].message.content}")

    except Exception as e:
        pytest.fail(f"Chat completion API call failed: {e}")


def test_openai_chat_completion_streaming_usage_delivery(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that OpenAI streaming chat completion automatically delivers usage payload to /track-usage."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(
        openai_client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )

    # Test streaming chat completion API
    try:
        stream = tracked_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Tell me a dad joke."}],
            max_tokens=50,
            stream=True,
        )

        print("Streaming chat completion response:")
        full_content = ""
        chunk_count = 0
        response_id = None

        for chunk in stream:
            chunk_count += 1
            if hasattr(chunk, "id") and chunk.id:
                response_id = chunk.id

            # Handle content chunks - check if choices exist and have content
            if (
                hasattr(chunk, "choices")
                and len(chunk.choices) > 0
                and hasattr(chunk.choices[0], "delta")
                and chunk.choices[0].delta.content is not None
            ):
                content = chunk.choices[0].delta.content
                full_content += content
                print(f"Chunk {chunk_count}: {content}")

            # Handle usage chunk - check if this is the final usage chunk
            if hasattr(chunk, "usage") and chunk.usage is not None:
                print(f"Usage chunk {chunk_count}: {chunk.usage}")

        print(f"Full streaming response: {full_content}")
        assert chunk_count > 0, "No chunks received in streaming response"
        assert full_content.strip(), "No content received in streaming response"

        # Verify that the usage event was delivered to the server
        if response_id:
            event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
            assert event is not None, (
                f"Streaming usage event for response_id {response_id} was not delivered to server"
            )

            # Verify event structure
            assert event.get("config_id") == "openai_chat"
            assert event.get("response_id") == response_id
            assert "usage" in event
            assert "timestamp" in event

    except Exception as e:
        pytest.fail(f"Streaming chat completion API call failed: {e}")


def test_openai_responses_api_usage_delivery(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that OpenAI responses API automatically delivers usage payload to /track-usage."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(
        openai_client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )

    # Force config refresh to get the latest server configuration
    tracked_client.config_manager.refresh()
    tracked_client.configs = tracked_client.config_manager.get_config(
        tracked_client.api_id
    )
    from aicostmanager.universal_extractor import UniversalExtractor

    tracked_client.extractor = UniversalExtractor(tracked_client.configs)

    # Test responses API (non-streaming)
    try:
        response = tracked_client.responses.create(
            model="gpt-3.5-turbo",
            input="Tell me a dad joke.",
        )

        print(f"Responses API response: {response}")
        assert response is not None
        assert hasattr(response, "output")
        assert len(response.output) > 0

        # Verify that the usage event was delivered to the server
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response.id)
        assert event is not None, (
            f"Responses API usage event for response_id {response.id} was not delivered to server"
        )

        # Verify event structure
        assert event.get("config_id") == "openai_responses"
        assert event.get("service_id") == response.model
        assert event.get("response_id") == response.id
        assert "usage" in event
        assert "timestamp" in event

        # Verify the response contains content
        output = response.output[0]
        assert hasattr(output, "content")
        assert len(output.content) > 0
        assert hasattr(output.content[0], "text")
        assert output.content[0].text is not None

        print(f"Dad joke responses API response: {output.content[0].text}")

    except Exception as e:
        pytest.fail(f"Responses API call failed: {e}")


def test_openai_responses_api_streaming_usage_delivery(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that OpenAI streaming responses API automatically delivers usage payload to /track-usage."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(
        openai_client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )

    # Force config refresh to get the latest server configuration
    tracked_client.config_manager.refresh()
    tracked_client.configs = tracked_client.config_manager.get_config(
        tracked_client.api_id
    )
    from aicostmanager.universal_extractor import UniversalExtractor

    tracked_client.extractor = UniversalExtractor(tracked_client.configs)

    # Test streaming responses API
    try:
        stream = tracked_client.responses.create(
            model="gpt-3.5-turbo",
            input="Tell me a dad joke.",
            stream=True,
        )

        print("Streaming responses API response:")
        full_content = ""
        chunk_count = 0
        response_id = None

        for chunk in stream:
            chunk_count += 1

            # Handle ResponseTextDeltaEvent which contains the actual text content
            if hasattr(chunk, "type") and chunk.type == "response.output_text.delta":
                if hasattr(chunk, "delta") and chunk.delta:
                    content = chunk.delta
                    full_content += content
                    print(f"Chunk {chunk_count}: {content}")

            # Also check for the final completed response
            elif hasattr(chunk, "type") and chunk.type == "response.completed":
                if hasattr(chunk, "response") and hasattr(chunk.response, "output"):
                    for output in chunk.response.output:
                        if hasattr(output, "content"):
                            for content_part in output.content:
                                if hasattr(content_part, "text") and content_part.text:
                                    print(f"Final response text: {content_part.text}")

                # Try to get response_id from the completed response
                if hasattr(chunk, "response") and hasattr(chunk.response, "id"):
                    response_id = chunk.response.id

        print(f"Full streaming responses API response: {full_content}")
        assert chunk_count > 0, "No chunks received in streaming responses API response"
        assert full_content.strip(), (
            "No content received in streaming responses API response"
        )

        # Verify that the usage event was delivered to the server
        if response_id:
            event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
            assert event is not None, (
                f"Streaming responses API usage event for response_id {response_id} was not delivered to server"
            )

            # Verify event structure
            assert event.get("config_id") == "openai_responses"
            assert event.get("response_id") == response_id
            assert "usage" in event
            assert "timestamp" in event

    except Exception as e:
        pytest.fail(f"Streaming responses API call failed: {e}")


def test_usage_payload_delivery_verification(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that usage payloads are properly formatted and delivered to /track-usage endpoint."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    openai_client = openai.OpenAI(api_key=openai_api_key)
    tracked_client = CostManager(
        openai_client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )

    # Make a test API call
    try:
        response = tracked_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Tell me a dad joke."}],
            max_tokens=50,
        )

        print(f"Chat completion response: {response}")
        assert response is not None
        assert hasattr(response, "choices")
        assert len(response.choices) > 0

        # Verify that the usage event was delivered to the server and validate structure
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response.id)
        assert event is not None, (
            f"Usage event for response_id {response.id} was not delivered to server"
        )

        # Verify the complete event structure
        assert "config_id" in event, "Event missing config_id"
        assert "service_id" in event, "Event missing service_id"
        assert "timestamp" in event, "Event missing timestamp"
        assert "response_id" in event, "Event missing response_id"
        assert "usage" in event, "Event missing usage data"

        # Verify specific values
        assert event.get("config_id") == "openai_chat"
        assert event.get("service_id") == response.model
        assert event.get("response_id") == response.id

        # Verify usage data structure
        usage = event["usage"]
        assert isinstance(usage, dict), "Usage data should be a dictionary"

        # Check for expected usage fields (may vary by provider)
        if "prompt_tokens" in usage:
            assert isinstance(usage["prompt_tokens"], (int, float)), (
                "prompt_tokens should be numeric"
            )
        if "completion_tokens" in usage:
            assert isinstance(usage["completion_tokens"], (int, float)), (
                "completion_tokens should be numeric"
            )
        if "total_tokens" in usage:
            assert isinstance(usage["total_tokens"], (int, float)), (
                "total_tokens should be numeric"
            )

        print("✅ Usage payload structure verification passed")
        print(f"Dad joke response: {response.choices[0].message.content}")

    except Exception as e:
        pytest.fail(f"Usage payload delivery verification failed: {e}")
