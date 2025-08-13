import os
import uuid

import json
import urllib.error
import urllib.request

VALID_PAYLOAD = {
    "prompt_tokens": 19,
    "completion_tokens": 10,
    "total_tokens": 29,
    "prompt_tokens_details": {
        "cached_tokens": 0,
        "audio_tokens": 0,
    },
    "completion_tokens_details": {
        "reasoning_tokens": 0,
        "audio_tokens": 0,
        "accepted_prediction_tokens": 0,
        "rejected_prediction_tokens": 0,
    },
}


def _post_track(api_key: str, api_base: str, payload: dict):
    api_url = os.getenv("AICM_API_URL", "/api/v1")
    url = f"{api_base.rstrip('/')}{api_url}/track"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("User-Agent", "aicostmanager-python")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:  # nosec: B310 - used for tests
            status = resp.getcode()
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:  # pragma: no cover - error path
        status = e.code
        body = e.read().decode("utf-8")
    return status, json.loads(body)


def test_track_single_event_success(aicm_api_key, aicm_api_base):
    body = {
        "tracked": [
            {
                "api_id": "openai_chat",
                "service_key": "openai::gpt-5-mini",
                "response_id": "evt1",
                "timestamp": "2025-01-01T00:00:00Z",
                "payload": VALID_PAYLOAD,
            }
        ]
    }
    status, data = _post_track(aicm_api_key, aicm_api_base, body)
    assert status == 201, data
    assert "event_ids" in data and len(data["event_ids"]) == 1
    result = data["event_ids"][0]
    assert "evt1" in result
    uuid.UUID(result["evt1"])  # validate uuid


def test_track_multiple_events_with_errors(aicm_api_key, aicm_api_base):
    events = [
        {
            "api_id": "openai_chat",
            "service_key": "openai::gpt-5-mini",
            "response_id": "ok1",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # Missing service_key
            "api_id": "openai_chat",
            "response_id": "missing",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # Invalid service_key format
            "api_id": "openai_chat",
            "service_key": "invalidformat",
            "response_id": "badformat",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # Service not found
            "api_id": "openai_chat",
            "service_key": "openai::does-not-exist",
            "response_id": "noservice",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # API client not found
            "api_id": "nonexistent_client",
            "service_key": "openai::gpt-5-mini",
            "response_id": "noapi",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": VALID_PAYLOAD,
        },
        {
            # Payload validation error (missing total_tokens)
            "api_id": "openai_chat",
            "service_key": "openai::gpt-5-mini",
            "response_id": "badpayload",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": {
                "prompt_tokens": 19,
                "completion_tokens": 10,
                "prompt_tokens_details": {
                    "cached_tokens": 0,
                    "audio_tokens": 0,
                },
                "completion_tokens_details": {
                    "reasoning_tokens": 0,
                    "audio_tokens": 0,
                    "accepted_prediction_tokens": 0,
                    "rejected_prediction_tokens": 0,
                },
            },
        },
    ]

    status, data = _post_track(aicm_api_key, aicm_api_base, {"tracked": events})
    assert status == 201, data
    assert "event_ids" in data and len(data["event_ids"]) == len(events)

    results = data["event_ids"]
    # Valid event returns UUID
    uuid.UUID(results[0]["ok1"])  # should not raise

    # Check error messages for each invalid event
    assert results[1]["missing"] == ["Missing service_key"]
    assert results[2]["badformat"] == ["Invalid service_key format"]
    assert results[3]["noservice"] == ["Service not found"]
    assert results[4]["noapi"] == ["API client not found"]
    err = results[5]["badpayload"]
    assert isinstance(err, list) and any(
        e.startswith("Payload validation error") for e in err
    )
