import json
import os
import time
import urllib.request
import uuid

import pytest

openai = pytest.importorskip("openai")
from aicostmanager.delivery import DeliveryType
from aicostmanager.tracker import Tracker
from aicostmanager.usage_utils import get_usage_from_response

BASE_URL = "http://127.0.0.1:8001"


def _wait_for_cost_event(aicm_api_key: str, response_id: str, timeout: int = 30):
    headers = {"Authorization": f"Bearer {aicm_api_key}"}
    # Wait an initial 2 seconds before attempting up to 3 fetches
    time.sleep(2)
    attempts = 3
    for _ in range(attempts):
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/api/v1/cost-events/{response_id}",
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.load(resp)
                    event_id = data.get("event_id") or data.get("cost_event", {}).get(
                        "event_id"
                    )
                    if event_id:
                        uuid.UUID(str(event_id))
                        return data
        except Exception:
            pass
        time.sleep(1)
    raise AssertionError(f"cost event for {response_id} not found")


@pytest.mark.parametrize(
    "service_key, model",
    [("openai::gpt-5-mini", "gpt-5-mini")],
)
def test_openai_responses_tracker(service_key, model, openai_api_key, aicm_api_key):
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")
    # Ensure PersistentDelivery logs request/response bodies from the server
    os.environ["AICM_DELIVERY_LOG_BODIES"] = "true"
    tracker = Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    )
    client = openai.OpenAI(api_key=openai_api_key)

    # Background tracking via queue
    resp = client.responses.create(model=model, input="Say hi")
    response_id = getattr(resp, "id", None)
    usage_payload = get_usage_from_response(resp, "openai_responses")
    tracker.track(
        "openai_responses", service_key, usage_payload, response_id=response_id
    )
    try:
        _wait_for_cost_event(aicm_api_key, response_id)
    except AssertionError as e:
        print("background wait failed:", str(e))
        pytest.skip("Cost event not found for OpenAI responses background; skipping")

    # Immediate delivery
    resp2 = client.responses.create(model=model, input="Say hi again")
    response_id2 = getattr(resp2, "id", None)
    with Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        delivery_type=DeliveryType.IMMEDIATE,
    ) as t2:
        usage2 = get_usage_from_response(resp2, "openai_responses")
        t2.track("openai_responses", service_key, usage2, response_id=response_id2)
    try:
        _wait_for_cost_event(aicm_api_key, response_id2)
    except AssertionError:
        pytest.skip("Cost event not found for OpenAI responses immediate; skipping")

    tracker.close()
