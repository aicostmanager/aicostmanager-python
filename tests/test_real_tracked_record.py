from aicostmanager import Tracker
from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager

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
    ini = IniManager("ini")
    dconfig = DeliveryConfig(
        ini_manager=ini,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
    )
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig)
    tracker = Tracker(aicm_api_key=aicm_api_key, ini_path="ini", delivery=delivery)
    response_id = "record-with-meta"

    dconfig2 = DeliveryConfig(
        ini_manager=IniManager("ini"),
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
    )
    delivery2 = create_delivery(DeliveryType.IMMEDIATE, dconfig2)
    with Tracker(aicm_api_key=aicm_api_key, ini_path="ini", delivery=delivery2) as t2:
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
    ini = IniManager("ini")
    dconfig = DeliveryConfig(
        ini_manager=ini,
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
    )
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig)
    tracker = Tracker(aicm_api_key=aicm_api_key, ini_path="ini", delivery=delivery)
    response_id = "record-without-meta"

    dconfig2 = DeliveryConfig(
        ini_manager=IniManager("ini"),
        aicm_api_key=aicm_api_key,
        aicm_api_base=aicm_api_base,
    )
    delivery2 = create_delivery(DeliveryType.IMMEDIATE, dconfig2)
    with Tracker(aicm_api_key=aicm_api_key, ini_path="ini", delivery=delivery2) as t2:
        t2.track(
            "openai_chat",
            "openai::gpt-5-mini",
            VALID_USAGE,
            response_id=response_id,
            timestamp="2025-01-01T00:00:00Z",
        )
    tracker.close()
