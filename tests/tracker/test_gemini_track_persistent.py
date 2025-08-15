import json
import time
import urllib.request
import uuid

import pytest

genai = pytest.importorskip("google.genai")

from aicostmanager.persistent_delivery import PersistentDelivery
from aicostmanager.tracker import Tracker
from aicostmanager.usage_utils import extract_usage, extract_stream_usage

BASE_URL = "http://127.0.0.1:8001"


def _wait_for_cost_event(aicm_api_key: str, response_id: str, timeout: int = 30):
    headers = {"Authorization": f"Bearer {aicm_api_key}"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/api/v1/cost-events/{response_id}", headers=headers
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


def test_gemini_track_non_streaming(google_api_key, aicm_api_key):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    delivery = PersistentDelivery(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    )
    tracker = Tracker(delivery=delivery)
    client = genai.Client(api_key=google_api_key)

    resp = client.models.generate_content(model="gemini-2.5-flash", contents="Say hi")
    response_id = getattr(resp, "id", None) or getattr(resp, "response_id", None)
    usage = extract_usage(resp)
    tracker.track("gemini", "google::gemini-2.5-flash", usage, response_id=response_id)
    _wait_for_cost_event(aicm_api_key, response_id)
    tracker.close()


def test_gemini_track_streaming(google_api_key, aicm_api_key):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    delivery = PersistentDelivery(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    )
    tracker = Tracker(delivery=delivery)
    client = genai.Client(api_key=google_api_key)

    stream = client.models.generate_content(
        model="gemini-2.5-flash", contents="Say hi", stream=True
    )
    usage, final_resp = extract_stream_usage(stream)
    response_id = getattr(final_resp, "id", None) or getattr(final_resp, "response_id", None)
    tracker.track("gemini", "google::gemini-2.5-flash", usage, response_id=response_id)
    _wait_for_cost_event(aicm_api_key, response_id)
    tracker.close()
