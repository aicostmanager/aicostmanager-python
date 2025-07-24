import json
import time

import pytest
import requests

anthropic = pytest.importorskip("anthropic")
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
    return anthropic.Anthropic(api_key=api_key)


def test_anthropic_cost_manager_configs(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    anth_configs = [c for c in configs if c.api_id == "anthropic"]
    assert anth_configs


def test_anthropic_config_retrieval_and_extractor_interaction(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    anth_configs = [cfg for cfg in configs if cfg.api_id == "anthropic"]
    assert anth_configs
    extractor = UniversalExtractor(anth_configs)
    for config in anth_configs:
        handling = config.handling_config
        assert isinstance(handling, dict)
        assert "tracked_methods" in handling
        assert "request_fields" in handling
        assert "response_fields" in handling
        assert "payload_mapping" in handling


def test_anthropic_messages_with_dad_joke(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(client)
    resp = tracked_client.messages.create(
        model="claude-3-haiku-20240307",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        max_tokens=100,
    )
    assert resp is not None
    assert hasattr(resp, "content")
    assert resp.content


def test_anthropic_messages_streaming_with_dad_joke(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(client)
    stream = tracked_client.messages.create(
        model="claude-3-haiku-20240307",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        max_tokens=100,
        stream=True,
    )
    full = ""
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        text = getattr(chunk, "text", None)
        if text:
            full += text
        if hasattr(chunk, "delta") and getattr(chunk.delta, "text", None):
            full += chunk.delta.text
    assert chunk_count > 0
    assert full.strip()


def test_anthropic_completion_with_dad_joke(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(client)
    resp = tracked_client.completions.create(
        model="claude-3-haiku-20240307",
        prompt="Tell me a dad joke.",
        max_tokens=100,
    )
    assert resp is not None
    assert hasattr(resp, "completion")


def test_anthropic_completion_streaming_with_dad_joke(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(client)
    stream = tracked_client.completions.create(
        model="claude-3-haiku-20240307",
        prompt="Tell me a dad joke.",
        max_tokens=100,
        stream=True,
    )
    chunk_count = 0
    full = ""
    for chunk in stream:
        chunk_count += 1
        text = getattr(chunk, "completion", None)
        if text:
            full += text
        if hasattr(chunk, "delta") and getattr(chunk.delta, "completion", None):
            full += chunk.delta.completion
    assert chunk_count > 0
    assert full.strip()


def test_anthropic_responses_api_with_dad_joke(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(client)
    resp = tracked_client.messages.create(
        model="claude-3-haiku-20240307",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
    )
    assert resp is not None
    assert hasattr(resp, "content")
    assert resp.content


def test_anthropic_responses_api_streaming_with_dad_joke(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(client)
    stream = tracked_client.messages.create(
        model="claude-3-haiku-20240307",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        stream=True,
    )
    full = ""
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        text = getattr(chunk, "text", None)
        if text:
            full += text
        if hasattr(chunk, "delta") and getattr(chunk.delta, "text", None):
            full += chunk.delta.text
    assert chunk_count > 0
    assert full.strip()


def test_extractor_payload_generation(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(client)
    configs = tracked_client.configs
    anth_configs = [cfg for cfg in configs if cfg.api_id == "anthropic"]
    extractor = UniversalExtractor(anth_configs)
    resp = tracked_client.messages.create(
        model="claude-3-haiku-20240307",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        max_tokens=50,
    )
    for config in anth_configs:
        tracking_data = extractor._build_tracking_data(
            config,
            "messages.create",
            (),
            {
                "model": "claude-3-haiku-20240307",
                "messages": [{"role": "user", "content": "Tell me a dad joke."}],
                "max_tokens": 50,
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


def test_anthropic_messages_usage_delivery(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )
    resp = tracked_client.messages.create(
        model="claude-3-haiku-20240307",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        max_tokens=50,
    )
    event = verify_event_delivered(aicm_api_key, aicm_api_base, resp.id)
    assert event is not None
    assert "usage" in event


def test_anthropic_messages_streaming_usage_delivery(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )
    stream = tracked_client.messages.create(
        model="claude-3-haiku-20240307",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        max_tokens=50,
        stream=True,
    )
    response_id = None
    full = ""
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        if hasattr(chunk, "id"):
            response_id = chunk.id
        text = getattr(chunk, "text", None)
        if text:
            full += text
        if hasattr(chunk, "delta") and getattr(chunk.delta, "text", None):
            full += chunk.delta.text
    assert chunk_count > 0
    assert full.strip()
    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None
        assert "usage" in event


def test_anthropic_responses_api_usage_delivery(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )
    resp = tracked_client.messages.create(
        model="claude-3-haiku-20240307",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
    )
    event = verify_event_delivered(aicm_api_key, aicm_api_base, resp.id)
    assert event is not None
    assert "usage" in event


def test_anthropic_responses_api_streaming_usage_delivery(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )
    stream = tracked_client.messages.create(
        model="claude-3-haiku-20240307",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        stream=True,
    )
    response_id = None
    full = ""
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        if hasattr(chunk, "id"):
            response_id = chunk.id
        text = getattr(chunk, "text", None)
        if text:
            full += text
        if hasattr(chunk, "delta") and getattr(chunk.delta, "text", None):
            full += chunk.delta.text
    assert chunk_count > 0
    assert full.strip()
    if response_id:
        event = verify_event_delivered(aicm_api_key, aicm_api_base, response_id)
        assert event is not None
        assert "usage" in event


def test_usage_payload_delivery_verification(anthropic_api_key, aicm_api_key, aicm_api_base, aicm_ini_path, clean_delivery):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    if not aicm_api_key:
        pytest.skip("AICM_API_KEY not set in .env file")
    client = _make_client(anthropic_api_key)
    tracked_client = CostManager(
        client,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        aicm_ini_path=aicm_ini_path,
    )
    resp = tracked_client.messages.create(
        model="claude-3-haiku-20240307",
        messages=[{"role": "user", "content": "Tell me a dad joke."}],
        max_tokens=50,
    )
    event = verify_event_delivered(aicm_api_key, aicm_api_base, resp.id)
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
