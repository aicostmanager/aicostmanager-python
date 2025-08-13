import time
import uuid

from aicostmanager import Tracker

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


def _make_tracker(api_key: str, api_base: str, tmp_path) -> Tracker:
    return Tracker(
        aicm_api_key=api_key,
        aicm_api_base=api_base,
        db_path=str(tmp_path / "queue.db"),
        poll_interval=0.1,
        batch_interval=0.1,
    )


def _wait_for_empty(delivery, timeout: float = 5.0) -> bool:
    for _ in range(int(timeout / 0.1)):
        if delivery.get_stats().get("queued", 0) == 0:
            return True
        time.sleep(0.1)
    return False


def test_track_single_event_success(aicm_api_key, aicm_api_base, tmp_path):
    tracker = _make_tracker(aicm_api_key, aicm_api_base, tmp_path)
    tracker.track(
        "openai_chat",
        "openai::gpt-5-mini",
        VALID_PAYLOAD,
        response_id="evt1",
        timestamp="2025-01-01T00:00:00Z",
    )
    assert _wait_for_empty(tracker.delivery)
    tracker.close()


def test_track_multiple_events_with_errors(aicm_api_key, aicm_api_base, tmp_path):
    tracker = _make_tracker(aicm_api_key, aicm_api_base, tmp_path)
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

    for event in events:
        tracker.track(
            event["api_id"],
            event.get("service_key"),
            event["payload"],
            response_id=event.get("response_id"),
            timestamp=event.get("timestamp"),
        )

    assert _wait_for_empty(tracker.delivery)
    tracker.close()


def test_deliver_now_single_event_success(aicm_api_key, aicm_api_base):
    tracker = Tracker(aicm_api_key=aicm_api_key, aicm_api_base=aicm_api_base)
    resp = tracker.deliver_now(
        "openai_chat",
        "openai::gpt-5-mini",
        VALID_PAYLOAD,
        response_id="evt1",
        timestamp="2025-01-01T00:00:00Z",
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "event_ids" in data and len(data["event_ids"]) == 1
    result = data["event_ids"][0]
    assert "evt1" in result
    uuid.UUID(result["evt1"])
    tracker.close()


def test_deliver_now_multiple_events_with_errors(aicm_api_key, aicm_api_base):
    tracker = Tracker(aicm_api_key=aicm_api_key, aicm_api_base=aicm_api_base)
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

    results = []
    for event in events:
        resp = tracker.deliver_now(
            event["api_id"],
            event.get("service_key"),
            event["payload"],
            response_id=event.get("response_id"),
            timestamp=event.get("timestamp"),
        )
        assert resp.status_code == 201, resp.text
        results.append(resp.json()["event_ids"][0])

    tracker.close()

    uuid.UUID(results[0]["ok1"])
    assert results[1]["missing"] == ["Missing service_key"]
    assert results[2]["badformat"] == ["Invalid service_key format"]
    assert results[3]["noservice"] == ["Service not found"]
    assert results[4]["noapi"] == ["API client not found"]
    err = results[5]["badpayload"]
    assert isinstance(err, list) and any(
        e.startswith("Payload validation error") for e in err
    )

