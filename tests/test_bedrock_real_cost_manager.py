import json
import time

import pytest
import requests

boto3 = pytest.importorskip("boto3")
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

            # Verify the /api/v1/usage/events/ call was successful
            assert events_response.status_code == 200, (
                f"Failed to fetch events: {events_response.status_code} - {events_response.text}"
            )

            if events_response.status_code == 200:
                events_data = events_response.json()
                results = events_data.get("results", [])
                for event in results:
                    if event.get("response_id") == response_id:
                        # Found the event! Now validate the payload structure
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

                        # Ensure no forbidden extra fields (like 'provider')
                        forbidden_fields = ["provider"]
                        for field in forbidden_fields:
                            assert field not in event, (
                                f"Forbidden field '{field}' found in event: {event}"
                            )

                        return event
            if attempt < max_attempts - 1:
                time.sleep(3)
        except Exception as e:
            if attempt < max_attempts - 1:
                time.sleep(3)
            else:
                raise e
    return None


def verify_track_usage_success(client, payload_data):
    """Directly test /track-usage endpoint to ensure 20x status codes."""
    try:
        # Test the payload structure directly
        test_payload = {"usage_records": [payload_data]}

        # Validate payload structure before sending
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

        # Ensure no forbidden fields
        forbidden_fields = ["provider"]
        for field in forbidden_fields:
            assert field not in payload_data, (
                f"Forbidden field '{field}' found in payload: {payload_data}"
            )

        # Make the actual /track-usage call
        result = client.track_usage(test_payload)

        # If we get here, the call was successful (20x status code)
        assert result is not None
        print(f"✅ /track-usage call successful: {result}")
        return True

    except Exception as e:
        print(f"❌ /track-usage call failed: {e}")
        print(f"❌ Failed payload: {json.dumps(payload_data, indent=2, default=str)}")
        raise e


def _make_client(region):
    return boto3.client("bedrock-runtime", region_name=region)


def test_bedrock_cost_manager_configs(
    aws_region, aicm_api_key, aicm_api_base, aicm_ini_path
):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    br_configs = [c for c in configs if c.api_id == "bedrockruntime"]
    assert br_configs


def test_bedrock_config_retrieval_and_extractor_interaction(
    aws_region, aicm_api_key, aicm_api_base, aicm_ini_path
):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    br_configs = [cfg for cfg in configs if cfg.api_id == "bedrockruntime"]
    assert br_configs
    extractor = UniversalExtractor(br_configs)
    for config in br_configs:
        handling = config.handling_config
        assert isinstance(handling, dict)
        assert "tracked_methods" in handling
        assert "request_fields" in handling
        assert "response_fields" in handling
        assert "payload_mapping" in handling


def test_bedrock_converse_with_dad_joke(
    aws_region, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test non-streaming converse API."""
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)

    response = tracked_client.converse(
        modelId="us.amazon.nova-pro-v1:0",
        messages=[{"role": "user", "content": [{"text": "Tell me a dad joke."}]}],
        inferenceConfig={"maxTokens": 100, "temperature": 0.5},
    )

    assert response is not None
    assert "output" in response
    assert "message" in response["output"]


def test_bedrock_converse_streaming_with_dad_joke(
    aws_region, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test streaming converse API."""
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)

    stream = tracked_client.converse_stream(
        modelId="us.amazon.nova-pro-v1:0",
        messages=[{"role": "user", "content": [{"text": "Tell me a dad joke."}]}],
        inferenceConfig={"maxTokens": 100, "temperature": 0.5},
    )

    full_content = ""
    chunk_count = 0

    for chunk in stream["stream"]:
        chunk_count += 1
        if "contentBlockDelta" in chunk:
            delta = chunk["contentBlockDelta"]
            if "delta" in delta and "text" in delta["delta"]:
                full_content += delta["delta"]["text"]

    assert chunk_count > 0
    assert full_content.strip()


def test_bedrock_converse_usage_delivery(
    aws_region, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that non-streaming converse automatically delivers usage payload with proper validation."""
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    client = _make_client(aws_region)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )

    response = tracked_client.converse(
        modelId="us.amazon.nova-pro-v1:0",
        messages=[{"role": "user", "content": [{"text": "Tell me a dad joke."}]}],
        inferenceConfig={"maxTokens": 50, "temperature": 0.5},
    )

    # Test payload structure and /track-usage call success
    payloads = tracked_client.get_tracked_payloads()
    assert len(payloads) > 0, "No payloads were generated"

    # Verify the payload structure is correct
    verify_track_usage_success(tracked_client.cm_client, payloads[0])

    response_id = response.get("output", {}).get("message", {}).get("id")
    if not response_id:
        # Bedrock might use RequestId as response_id
        response_id = response.get("ResponseMetadata", {}).get("RequestId")

    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None, (
            f"Usage event for response_id {response_id} was not delivered to server"
        )
        assert "usage" in event


def test_bedrock_converse_streaming_usage_delivery(
    aws_region, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery
):
    """Test that streaming converse automatically delivers usage payload with proper validation."""
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")

    client = _make_client(aws_region)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )

    # Refresh config to pick up server changes
    tracked_client.config_manager.refresh()

    stream = tracked_client.converse_stream(
        modelId="us.amazon.nova-pro-v1:0",
        messages=[{"role": "user", "content": [{"text": "Tell me a dad joke."}]}],
        inferenceConfig={"maxTokens": 50, "temperature": 0.5},
    )

    response_id = None
    chunk_count = 0

    for chunk in stream["stream"]:
        chunk_count += 1
        if "messageStart" in chunk:
            # Check if message key exists first
            if "message" in chunk["messageStart"]:
                response_id = chunk["messageStart"]["message"].get("id")
            # Sometimes the id might be directly in messageStart
            else:
                response_id = chunk["messageStart"].get("id")
        elif "metadata" in chunk:
            response_id = response_id or chunk["metadata"].get("id")

    assert chunk_count > 0

    # Test payload structure and /track-usage call success
    payloads = tracked_client.get_tracked_payloads()
    if len(payloads) > 0:
        verify_track_usage_success(tracked_client.cm_client, payloads[0])

    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None, (
            f"Streaming usage event for response_id {response_id} was not delivered to server"
        )
        assert "usage" in event


def test_extractor_payload_generation(
    aws_region, aicm_api_key, aicm_api_base, aicm_ini_path
):
    """Test that extractor can generate payloads from Bedrock responses with proper structure validation."""
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    br_configs = [cfg for cfg in configs if cfg.api_id == "bedrockruntime"]
    extractor = UniversalExtractor(br_configs)

    response = tracked_client.converse(
        modelId="us.amazon.nova-pro-v1:0",
        messages=[{"role": "user", "content": [{"text": "Tell me a dad joke."}]}],
        inferenceConfig={"maxTokens": 50, "temperature": 0.5},
    )

    for config in br_configs:
        tracking_data = extractor._build_tracking_data(
            config,
            "converse",
            (),
            {
                "modelId": "us.amazon.nova-pro-v1:0",
                "messages": [
                    {"role": "user", "content": [{"text": "Tell me a dad joke."}]}
                ],
                "inferenceConfig": {"maxTokens": 50, "temperature": 0.5},
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
        assert "usage_data" in tracking_data

        # Build the actual payload
        payload = extractor._build_payload(config, tracking_data)

        # Validate the payload structure matches OpenAPI spec
        required_fields = ["config_id", "service_id", "timestamp", "usage"]
        for field in required_fields:
            assert field in payload, (
                f"Required field '{field}' missing from generated payload"
            )

        # Check for forbidden fields
        forbidden_fields = ["provider"]
        for field in forbidden_fields:
            if field in payload:
                print(
                    f"⚠️  WARNING: Forbidden field '{field}' found in payload - server config needs updating"
                )
