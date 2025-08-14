import time
import json
import uuid
import urllib.request

import pytest

genai = pytest.importorskip("google.genai")

from aicostmanager.tracker import Tracker

BASE_URL = "http://127.0.0.1:8001"


def _wait_for_cost_event(aicm_api_key: str, response_id: str, timeout: int = 30):
    headers = {"Authorization": f"Bearer {aicm_api_key}"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/api/v1/cost-events/{response_id}",
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.load(resp)
                    event_id = data.get("event_id") or data.get("cost_event", {}).get("event_id")
                    if event_id:
                        uuid.UUID(str(event_id))
                        return data
        except Exception:
            pass
        time.sleep(1)
    raise AssertionError(f"cost event for {response_id} not found")


@pytest.mark.parametrize(
    "service_key, model",
    [("google::gemini-2.5-flash", "gemini-2.5-flash")],
)
def test_gemini_tracker(service_key, model, google_api_key, aicm_api_key):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    tracker = Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    )
    client = genai.Client(api_key=google_api_key)

    response = client.models.generate_content(model=model, contents="Say hi")
    response_id = getattr(response, "id", None) or getattr(response, "response_id", None)
    if not response_id:
        pytest.skip("No response_id returned by Gemini")
    tracker.track("gemini", service_key, {"input_tokens": 1}, response_id=response_id)
    _wait_for_cost_event(aicm_api_key, response_id)

    response2 = client.models.generate_content(model=model, contents="Say hi again")
    response_id2 = getattr(response2, "id", None) or getattr(response2, "response_id", None)
    if not response_id2:
        pytest.skip("No response_id returned by Gemini")
    delivery_resp = tracker.deliver_now(
        "gemini", service_key, {"input_tokens": 1}, response_id=response_id2
    )
    assert delivery_resp.status_code in (200, 201)
    _wait_for_cost_event(aicm_api_key, response_id2)

    tracker.close()
