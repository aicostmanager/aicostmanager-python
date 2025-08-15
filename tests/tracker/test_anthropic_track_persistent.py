import json
import os
import time
import urllib.request
import uuid

import pytest

anthropic = pytest.importorskip("anthropic")

from aicostmanager.persistent_delivery import PersistentDelivery
from aicostmanager.tracker import Tracker
from aicostmanager.usage_utils import extract_usage, extract_stream_usage

BASE_URL = os.environ.get("AICM_API_BASE", "http://127.0.0.1:8001")


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


def test_anthropic_track_non_streaming(anthropic_api_key, aicm_api_key, tmp_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    delivery = PersistentDelivery(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        db_path=str(tmp_path / "anthropic_queue.db"),
        poll_interval=0.1,
        batch_interval=0.1,
    )
    tracker = Tracker(delivery=delivery)
    client = anthropic.Anthropic(api_key=anthropic_api_key)

    resp = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        messages=[{"role": "user", "content": "Say hi"}],
        max_tokens=20,
    )
    response_id = getattr(resp, "id", None)
    usage = extract_usage(resp)
    tracker.track("anthropic", "anthropic::claude-3-5-sonnet-20241022", usage, response_id=response_id)
    _wait_for_cost_event(aicm_api_key, response_id)
    tracker.close()


def test_anthropic_track_streaming(anthropic_api_key, aicm_api_key, tmp_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    delivery = PersistentDelivery(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        db_path=str(tmp_path / "anthropic_queue.db"),
        poll_interval=0.1,
        batch_interval=0.1,
    )
    tracker = Tracker(delivery=delivery)
    client = anthropic.Anthropic(api_key=anthropic_api_key)

    with client.messages.stream(
        model="claude-3-5-sonnet-20241022",
        messages=[{"role": "user", "content": "Say hi"}],
        max_tokens=20,
    ) as stream:
        usage, final_msg = extract_stream_usage(stream)
    response_id = getattr(final_msg, "id", None)
    tracker.track("anthropic", "anthropic::claude-3-5-sonnet-20241022", usage, response_id=response_id)
    _wait_for_cost_event(aicm_api_key, response_id)
    tracker.close()
