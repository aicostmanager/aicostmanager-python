from aicostmanager import Tracker
from aicostmanager.delivery import DeliveryType

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

    with Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        delivery_type=DeliveryType.IMMEDIATE,
    ) as t2:
        t2.track(
            "openai_chat",
            "openai::gpt-5-mini",
            VALID_USAGE,
            response_id=response_id,
            client_customer_key="c1",
            context={"foo": "bar"},
            timestamp="2025-01-01T00:00:00Z",
        )
    tracker.close()


def test_deliver_now_without_client_customer_key_and_context(
    aicm_api_key, aicm_api_base
):
    tracker = Tracker(aicm_api_key=aicm_api_key, aicm_api_base=aicm_api_base)
    response_id = "record-without-meta"

    with Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
        delivery_type=DeliveryType.IMMEDIATE,
    ) as t2:
        t2.track(
            "openai_chat",
            "openai::gpt-5-mini",
            VALID_USAGE,
            response_id=response_id,
            timestamp="2025-01-01T00:00:00Z",
        )
    tracker.close()
