import uuid

from aicostmanager import Tracker

# A valid usage payload for the /track endpoint
VALID_USAGE = {
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


def test_deliver_now_with_client_customer_key_and_context(aicm_api_key, aicm_api_base):
    tracker = Tracker(aicm_api_key=aicm_api_key, aicm_api_base=aicm_api_base)
    response_id = "record-with-meta"

    resp = tracker.deliver_now(
        "openai_chat",
        "openai::gpt-5-mini",
        VALID_USAGE,
        response_id=response_id,
        client_customer_key="c1",
        context={"foo": "bar"},
        timestamp="2025-01-01T00:00:00Z",
    )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "event_ids" in data and len(data["event_ids"]) == 1
    result = data["event_ids"][0]
    assert response_id in result
    uuid.UUID(result[response_id])
    tracker.close()


def test_deliver_now_without_client_customer_key_and_context(
    aicm_api_key, aicm_api_base
):
    tracker = Tracker(aicm_api_key=aicm_api_key, aicm_api_base=aicm_api_base)
    response_id = "record-without-meta"

    resp = tracker.deliver_now(
        "openai_chat",
        "openai::gpt-5-mini",
        VALID_USAGE,
        response_id=response_id,
        timestamp="2025-01-01T00:00:00Z",
    )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "event_ids" in data and len(data["event_ids"]) == 1
    result = data["event_ids"][0]
    assert response_id in result
    uuid.UUID(result[response_id])
    tracker.close()
