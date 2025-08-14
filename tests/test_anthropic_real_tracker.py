import time
import uuid

import json
import urllib.request

import pytest

anthropic = pytest.importorskip("anthropic")
from aicostmanager.tracker import Tracker

BASE_URL = "http://127.0.0.1:8001"


def _wait_for_cost_event(aicm_api_key: str, response_id: str, timeout: int = 30):
    """Poll the server until a cost event for ``response_id`` appears."""
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
    [
        ("anthropic::claude-sonnet-4-20250514", "claude-3-haiku-20240307"),
        ("anthropic::claude-sonnet-4", "claude-3-haiku-20240307"),
    ],
)
def test_anthropic_tracker(service_key, model, anthropic_api_key, aicm_api_key):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    tracker = Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    )
    client = anthropic.Anthropic(api_key=anthropic_api_key)

    # Background tracking via queue
    resp = client.messages.create(
        model=model,
        messages=[{"role": "user", "content": "Say hi"}],
        max_tokens=20,
    )
    response_id = resp.id
    tracker.track("anthropic", service_key, {"input_tokens": 1}, response_id=response_id)
    _wait_for_cost_event(aicm_api_key, response_id)

    # Immediate delivery
    resp2 = client.messages.create(
        model=model,
        messages=[{"role": "user", "content": "Say hi again"}],
        max_tokens=20,
    )
    response_id2 = resp2.id
    delivery_resp = tracker.deliver_now(
        "anthropic", service_key, {"input_tokens": 1}, response_id=response_id2
    )
    assert delivery_resp.status_code in (200, 201)
    _wait_for_cost_event(aicm_api_key, response_id2)

    tracker.close()
