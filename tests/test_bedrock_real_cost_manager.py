import json
import time

import pytest
import requests

boto3 = pytest.importorskip("boto3")
from aicostmanager import CostManager, UniversalExtractor


def verify_event_delivered(aicm_api_key, aicm_api_base, response_id, timeout=10, max_attempts=8):
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
            if events_response.status_code == 200:
                events_data = events_response.json()
                results = events_data.get("results", [])
                for event in results:
                    if event.get("response_id") == response_id:
                        return event
            if attempt < max_attempts - 1:
                time.sleep(3)
        except Exception:
            if attempt < max_attempts - 1:
                time.sleep(3)
    return None


def _make_client(region):
    return boto3.client("bedrock-runtime", region_name=region)


def _invoke(client, model_id, prompt, stream=False):
    body = {
        "prompt": prompt,
        "max_gen_len": 100,
        "temperature": 0.5,
    }
    if stream:
        response = client.invoke_model_with_response_stream(
            modelId=model_id,
            body=json.dumps(body),
            accept="application/json",
            contentType="application/json",
        )
        return response["body"]
    else:
        resp = client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            accept="application/json",
            contentType="application/json",
        )
        return json.loads(resp["body"].read())


def test_bedrock_cost_manager_configs(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    br_configs = [c for c in configs if c.api_id == "bedrock"]
    assert br_configs


def test_bedrock_config_retrieval_and_extractor_interaction(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    br_configs = [cfg for cfg in configs if cfg.api_id == "bedrock"]
    assert br_configs
    extractor = UniversalExtractor(br_configs)
    for config in br_configs:
        handling = config.handling_config
        assert isinstance(handling, dict)
        assert "tracked_methods" in handling
        assert "request_fields" in handling
        assert "response_fields" in handling
        assert "payload_mapping" in handling


def test_bedrock_invoke_model_with_dad_joke(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)
    resp = _invoke(tracked_client, "us.meta.llama3-3-70b-instruct-v1:0", "Tell me a dad joke.")
    assert resp


def test_bedrock_invoke_model_streaming_with_dad_joke(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)
    stream = _invoke(tracked_client, "us.meta.llama3-3-70b-instruct-v1:0", "Tell me a dad joke.", stream=True)
    full = ""
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        if "bytes" in chunk:
            try:
                data = json.loads(chunk["bytes"].decode("utf-8"))
                text = data.get("generation") or data.get("output")
                if text:
                    full += text
            except Exception:
                pass
    assert chunk_count > 0
    assert full.strip()


def test_bedrock_completion_with_dad_joke(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)
    resp = _invoke(tracked_client, "us.amazon.nova-pro-v1:0", "Tell me a dad joke.")
    assert resp


def test_bedrock_completion_streaming_with_dad_joke(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)
    stream = _invoke(tracked_client, "us.amazon.nova-pro-v1:0", "Tell me a dad joke.", stream=True)
    chunk_count = 0
    full = ""
    for chunk in stream:
        chunk_count += 1
        if "bytes" in chunk:
            try:
                data = json.loads(chunk["bytes"].decode("utf-8"))
                text = data.get("generation") or data.get("output")
                if text:
                    full += text
            except Exception:
                pass
    assert chunk_count > 0
    assert full.strip()


def test_bedrock_responses_api_with_dad_joke(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)
    resp = _invoke(tracked_client, "us.amazon.nova-pro-v1:0", "Tell me a dad joke.")
    assert resp


def test_bedrock_responses_api_streaming_with_dad_joke(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)
    stream = _invoke(tracked_client, "us.amazon.nova-pro-v1:0", "Tell me a dad joke.", stream=True)
    chunk_count = 0
    full = ""
    for chunk in stream:
        chunk_count += 1
        if "bytes" in chunk:
            try:
                data = json.loads(chunk["bytes"].decode("utf-8"))
                text = data.get("generation") or data.get("output")
                if text:
                    full += text
            except Exception:
                pass
    assert chunk_count > 0
    assert full.strip()


def test_extractor_payload_generation(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not aws_region:
        pytest.skip("AWS_DEFAULT_REGION not set in .env file")
    client = _make_client(aws_region)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    br_configs = [cfg for cfg in configs if cfg.api_id == "bedrock"]
    extractor = UniversalExtractor(br_configs)
    resp = _invoke(tracked_client, "us.meta.llama3-3-70b-instruct-v1:0", "Tell me a dad joke.")
    for config in br_configs:
        tracking_data = extractor._build_tracking_data(
            config,
            "invoke_model",
            (),
            {
                "modelId": "us.meta.llama3-3-70b-instruct-v1:0",
                "prompt": "Tell me a dad joke.",
            },
            resp,
            client,
        )
        assert "timestamp" in tracking_data
        assert "method" in tracking_data
        assert "config_identifier" in tracking_data
        assert "request_data" in tracking_data
        assert "response_data" in tracking_data
        assert "client_data" in tracking_data
        assert "usage_data" in tracking_data


def test_bedrock_invoke_model_usage_delivery(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
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
    resp = _invoke(tracked_client, "us.meta.llama3-3-70b-instruct-v1:0", "Tell me a dad joke.")
    response_id = resp.get("response_id") or resp.get("id")
    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None
        assert "usage" in event


def test_bedrock_invoke_model_streaming_usage_delivery(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
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
    stream = _invoke(tracked_client, "us.meta.llama3-3-70b-instruct-v1:0", "Tell me a dad joke.", stream=True)
    response_id = None
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        if "bytes" in chunk:
            try:
                data = json.loads(chunk["bytes"].decode("utf-8"))
                response_id = response_id or data.get("response_id")
            except Exception:
                pass
    assert chunk_count > 0
    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None
        assert "usage" in event


def test_bedrock_responses_api_usage_delivery(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
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
    resp = _invoke(tracked_client, "us.amazon.nova-pro-v1:0", "Tell me a dad joke.")
    response_id = resp.get("response_id") or resp.get("id")
    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None
        assert "usage" in event


def test_bedrock_responses_api_streaming_usage_delivery(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
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
    stream = _invoke(tracked_client, "us.amazon.nova-pro-v1:0", "Tell me a dad joke.", stream=True)
    response_id = None
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        if "bytes" in chunk:
            try:
                data = json.loads(chunk["bytes"].decode("utf-8"))
                response_id = response_id or data.get("response_id")
            except Exception:
                pass
    assert chunk_count > 0
    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None
        assert "usage" in event


def test_usage_payload_delivery_verification(aws_region, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
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
    resp = _invoke(tracked_client, "us.meta.llama3-3-70b-instruct-v1:0", "Tell me a dad joke.")
    response_id = resp.get("response_id") or resp.get("id")
    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None
        assert "usage" in event
        usage = event["usage"]
        assert isinstance(usage, dict)
        if "prompt_tokens" in usage:
            assert isinstance(usage["prompt_tokens"], (int, float))
        if "completion_tokens" in usage:
            assert isinstance(usage["completion_tokens"], (int, float))
        if "total_tokens" in usage:
            assert isinstance(usage["total_tokens"], (int, float))
