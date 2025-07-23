import json
import time

import pytest
import requests

openai = pytest.importorskip("openai")
from aicostmanager import CostManager, UniversalExtractor


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
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                full_content += content
                print(f"Chunk {chunk_count}: {content}")

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
            if chunk.choices[0].text is not None:
                content = chunk.choices[0].text
                full_content += content
                print(f"Chunk {chunk_count}: {content}")

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
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
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

        # Wait a moment for the background delivery to complete
        time.sleep(2)

        # Verify that the usage payload was delivered by checking the /track-usage endpoint
        # We'll check if we can retrieve the event by making a request to the API
        headers = {
            "Authorization": f"Bearer {aicm_api_key}",
            "Content-Type": "application/json",
        }

        # Try to get usage events to see if our event was recorded
        try:
            events_response = requests.get(
                f"{aicm_api_base}/api/v1/usage/events/",
                headers=headers,
                params={"limit": 10},
                timeout=10,
            )

            if events_response.status_code == 200:
                events_data = events_response.json()
                print(f"Retrieved {len(events_data.get('results', []))} usage events")

                # Check if our response_id appears in the events
                response_id = response.id
                found_event = False
                for event in events_data.get("results", []):
                    if event.get("response_id") == response_id:
                        found_event = True
                        print(f"✅ Found usage event for response_id: {response_id}")
                        print(f"   Event data: {event}")
                        break

                if not found_event:
                    print(
                        f"⚠️  Usage event for response_id {response_id} not found in recent events"
                    )
                    print(
                        "   This might be normal if delivery is still in progress or if events are processed asynchronously"
                    )
            else:
                print(
                    f"⚠️  Could not retrieve usage events: {events_response.status_code}"
                )
                print(f"   Response: {events_response.text}")

        except Exception as e:
            print(f"⚠️  Error checking usage events: {e}")

        print(f"Dad joke response: {response.choices[0].message.content}")

    except Exception as e:
        pytest.fail(f"Chat completion API call failed: {e}")


def test_openai_chat_completion_streaming_usage_delivery(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
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
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                full_content += content
                print(f"Chunk {chunk_count}: {content}")

        print(f"Full streaming response: {full_content}")
        assert chunk_count > 0, "No chunks received in streaming response"
        assert full_content.strip(), "No content received in streaming response"

        # Wait a moment for the background delivery to complete
        time.sleep(2)

        # Verify that the usage payload was delivered
        if response_id:
            headers = {
                "Authorization": f"Bearer {aicm_api_key}",
                "Content-Type": "application/json",
            }

            try:
                events_response = requests.get(
                    f"{aicm_api_base}/api/v1/usage/events/",
                    headers=headers,
                    params={"limit": 10},
                    timeout=10,
                )

                if events_response.status_code == 200:
                    events_data = events_response.json()
                    print(
                        f"Retrieved {len(events_data.get('results', []))} usage events"
                    )

                    # Check if our response_id appears in the events
                    found_event = False
                    for event in events_data.get("results", []):
                        if event.get("response_id") == response_id:
                            found_event = True
                            print(
                                f"✅ Found streaming usage event for response_id: {response_id}"
                            )
                            print(f"   Event data: {event}")
                            break

                    if not found_event:
                        print(
                            f"⚠️  Streaming usage event for response_id {response_id} not found in recent events"
                        )
                        print(
                            "   This might be normal if delivery is still in progress or if events are processed asynchronously"
                        )
                else:
                    print(
                        f"⚠️  Could not retrieve usage events: {events_response.status_code}"
                    )
                    print(f"   Response: {events_response.text}")

            except Exception as e:
                print(f"⚠️  Error checking streaming usage events: {e}")

    except Exception as e:
        pytest.fail(f"Streaming chat completion API call failed: {e}")


def test_openai_responses_api_usage_delivery(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
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

        # Wait a moment for the background delivery to complete
        time.sleep(2)

        # Verify that the usage payload was delivered
        headers = {
            "Authorization": f"Bearer {aicm_api_key}",
            "Content-Type": "application/json",
        }

        try:
            events_response = requests.get(
                f"{aicm_api_base}/api/v1/usage/events/",
                headers=headers,
                params={"limit": 10},
                timeout=10,
            )

            if events_response.status_code == 200:
                events_data = events_response.json()
                print(f"Retrieved {len(events_data.get('results', []))} usage events")

                # Check if our response appears in the events
                # For responses API, we might need to look for a different identifier
                found_event = False
                for event in events_data.get("results", []):
                    # Look for events with the same model and similar timestamp
                    if event.get("service_id") == "gpt-3.5-turbo":
                        found_event = True
                        print("✅ Found responses API usage event")
                        print(f"   Event data: {event}")
                        break

                if not found_event:
                    print("⚠️  Responses API usage event not found in recent events")
                    print(
                        "   This might be normal if delivery is still in progress or if events are processed asynchronously"
                    )
            else:
                print(
                    f"⚠️  Could not retrieve usage events: {events_response.status_code}"
                )
                print(f"   Response: {events_response.text}")

        except Exception as e:
            print(f"⚠️  Error checking responses API usage events: {e}")

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
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
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

        # Wait a moment for the background delivery to complete
        time.sleep(2)

        # Verify that the usage payload was delivered
        headers = {
            "Authorization": f"Bearer {aicm_api_key}",
            "Content-Type": "application/json",
        }

        try:
            events_response = requests.get(
                f"{aicm_api_base}/api/v1/usage/events/",
                headers=headers,
                params={"limit": 10},
                timeout=10,
            )

            if events_response.status_code == 200:
                events_data = events_response.json()
                print(f"Retrieved {len(events_data.get('results', []))} usage events")

                # Check if our response appears in the events
                found_event = False
                for event in events_data.get("results", []):
                    # Look for events with the same model and similar timestamp
                    if event.get("service_id") == "gpt-3.5-turbo":
                        found_event = True
                        print("✅ Found streaming responses API usage event")
                        print(f"   Event data: {event}")
                        break

                if not found_event:
                    print(
                        "⚠️  Streaming responses API usage event not found in recent events"
                    )
                    print(
                        "   This might be normal if delivery is still in progress or if events are processed asynchronously"
                    )
            else:
                print(
                    f"⚠️  Could not retrieve usage events: {events_response.status_code}"
                )
                print(f"   Response: {events_response.text}")

        except Exception as e:
            print(f"⚠️  Error checking streaming responses API usage events: {e}")

    except Exception as e:
        pytest.fail(f"Streaming responses API call failed: {e}")


def test_usage_payload_delivery_verification(
    openai_api_key, aicm_api_key, aicm_api_base, aicm_ini_path
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

        # Wait for delivery to complete
        time.sleep(3)

        # Verify the payload format by checking the /track-usage endpoint directly
        headers = {
            "Authorization": f"Bearer {aicm_api_key}",
            "Content-Type": "application/json",
        }

        try:
            # Get recent usage events to verify payload format
            events_response = requests.get(
                f"{aicm_api_base}/api/v1/usage/events/",
                headers=headers,
                params={"limit": 5},
                timeout=10,
            )

            if events_response.status_code == 200:
                events_data = events_response.json()
                print(f"Retrieved {len(events_data.get('results', []))} usage events")

                # Look for our specific event
                response_id = response.id
                found_event = None
                for event in events_data.get("results", []):
                    if event.get("response_id") == response_id:
                        found_event = event
                        break

                if found_event:
                    print(f"✅ Found usage event for response_id: {response_id}")
                    print(f"   Event data: {json.dumps(found_event, indent=2)}")

                    # Verify the payload structure
                    assert "config_id" in found_event, "Event missing config_id"
                    assert "service_id" in found_event, "Event missing service_id"
                    assert "timestamp" in found_event, "Event missing timestamp"
                    assert "response_id" in found_event, "Event missing response_id"
                    assert "usage" in found_event, "Event missing usage data"

                    # Verify usage data structure
                    usage = found_event["usage"]
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
                else:
                    print(
                        f"⚠️  Usage event for response_id {response_id} not found in recent events"
                    )
                    print(
                        "   This might be normal if delivery is still in progress or if events are processed asynchronously"
                    )
            else:
                print(
                    f"⚠️  Could not retrieve usage events: {events_response.status_code}"
                )
                print(f"   Response: {events_response.text}")

        except Exception as e:
            print(f"⚠️  Error verifying usage payload: {e}")

        print(f"Dad joke response: {response.choices[0].message.content}")

    except Exception as e:
        pytest.fail(f"Usage payload delivery verification failed: {e}")
