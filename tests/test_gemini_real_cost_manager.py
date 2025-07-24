import json
import time

import pytest
import requests

genai = pytest.importorskip("google.generativeai")
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


def _make_client(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-pro")


def test_gemini_cost_manager_configs(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_client(google_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    gem_configs = [c for c in configs if c.api_id == "gemini"]
    assert gem_configs


def test_gemini_config_retrieval_and_extractor_interaction(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_client(google_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    gem_configs = [cfg for cfg in configs if cfg.api_id == "gemini"]
    assert gem_configs
    extractor = UniversalExtractor(gem_configs)
    for config in gem_configs:
        handling = config.handling_config
        assert isinstance(handling, dict)
        assert "tracked_methods" in handling
        assert "request_fields" in handling
        assert "response_fields" in handling
        assert "payload_mapping" in handling


def test_gemini_generate_content_with_dad_joke(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_client(google_api_key)
    tracked_client = CostManager(client)
    resp = tracked_client.generate_content("Tell me a dad joke.")
    assert resp is not None
    text = getattr(resp, "text", None)
    assert text


def test_gemini_generate_content_streaming_with_dad_joke(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_client(google_api_key)
    tracked_client = CostManager(client)
    stream = tracked_client.generate_content("Tell me a dad joke.", stream=True)
    full = ""
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        text = getattr(chunk, "text", None)
        if text:
            full += text
    assert chunk_count > 0
    assert full.strip()


def test_gemini_completion_with_dad_joke(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_client(google_api_key)
    tracked_client = CostManager(client)
    resp = tracked_client.generate_content("Tell me a dad joke.")
    assert resp is not None
    assert getattr(resp, "text", None)


def test_gemini_completion_streaming_with_dad_joke(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_client(google_api_key)
    tracked_client = CostManager(client)
    stream = tracked_client.generate_content("Tell me a dad joke.", stream=True)
    full = ""
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        text = getattr(chunk, "text", None)
        if text:
            full += text
    assert chunk_count > 0
    assert full.strip()


def test_gemini_responses_api_with_dad_joke(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_client(google_api_key)
    tracked_client = CostManager(client)
    resp = tracked_client.generate_content("Tell me a dad joke.")
    assert resp is not None
    assert getattr(resp, "text", None)


def test_gemini_responses_api_streaming_with_dad_joke(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_client(google_api_key)
    tracked_client = CostManager(client)
    stream = tracked_client.generate_content("Tell me a dad joke.", stream=True)
    full = ""
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        text = getattr(chunk, "text", None)
        if text:
            full += text
    assert chunk_count > 0
    assert full.strip()


def test_extractor_payload_generation(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    client = _make_client(google_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    gem_configs = [cfg for cfg in configs if cfg.api_id == "gemini"]
    extractor = UniversalExtractor(gem_configs)
    resp = tracked_client.generate_content("Tell me a dad joke.")
    for config in gem_configs:
        tracking_data = extractor._build_tracking_data(
            config,
            "generate_content",
            (),
            {"prompt": "Tell me a dad joke."},
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


def test_gemini_generate_content_usage_delivery(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
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
    resp = tracked_client.generate_content("Tell me a dad joke.")
    event = verify_event_delivered(aicm_api_key, aicm_api_base, resp.response_id)
    assert event is not None
    assert "usage" in event


def test_gemini_generate_content_streaming_usage_delivery(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
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
    stream = tracked_client.generate_content("Tell me a dad joke.", stream=True)
    response_id = None
    full = ""
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        if hasattr(chunk, "response_id"):
            response_id = chunk.response_id
        text = getattr(chunk, "text", None)
        if text:
            full += text
    assert chunk_count > 0
    assert full.strip()
    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None
        assert "usage" in event


def test_gemini_responses_api_usage_delivery(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
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
    resp = tracked_client.generate_content("Tell me a dad joke.")
    event = verify_event_delivered(aicm_api_key, aicm_api_base, resp.response_id)
    assert event is not None
    assert "usage" in event


def test_gemini_responses_api_streaming_usage_delivery(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
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
    stream = tracked_client.generate_content("Tell me a dad joke.", stream=True)
    response_id = None
    full = ""
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        if hasattr(chunk, "response_id"):
            response_id = chunk.response_id
        text = getattr(chunk, "text", None)
        if text:
            full += text
    assert chunk_count > 0
    assert full.strip()
    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None
        assert "usage" in event


def test_usage_payload_delivery_verification(google_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
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
    resp = tracked_client.generate_content("Tell me a dad joke.")
    event = verify_event_delivered(aicm_api_key, aicm_api_base, resp.response_id)
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
