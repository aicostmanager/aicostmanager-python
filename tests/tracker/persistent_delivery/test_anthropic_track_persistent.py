import json
import os
import time
import urllib.request
import uuid

import pytest

anthropic = pytest.importorskip("anthropic")

from aicostmanager.tracker import Tracker

BASE_URL = os.environ.get("AICM_API_BASE", "http://127.0.0.1:8001")


def _wait_for_cost_event(aicm_api_key: str, response_id: str, timeout: int = 30):
    headers = {
        "Authorization": f"Bearer {aicm_api_key}",
        "Content-Type": "application/json",
    }
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/api/v1/cost-events/{response_id}",
                headers=headers,
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.load(resp)
                    print(f"Response data: {data}")

                    # Handle both array and single object responses
                    if isinstance(data, list) and len(data) > 0:
                        # Server returns array of cost events
                        first_event = data[0]
                        event_id = first_event.get("event_id") or first_event.get(
                            "uuid"
                        )
                        if event_id:
                            uuid.UUID(str(event_id))
                            return data
                    else:
                        # Handle single object response (fallback)
                        event_id = data.get("event_id") or data.get(
                            "cost_event", {}
                        ).get("event_id")
                        if event_id:
                            uuid.UUID(str(event_id))
                            return data
        except Exception as e:
            print(f"Error checking cost event: {e}")
        time.sleep(1)
    raise AssertionError(f"cost event for {response_id} not found")


def test_anthropic_track_non_streaming(anthropic_api_key, aicm_api_key, tmp_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    with Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        db_path=str(tmp_path / "anthropic_queue.db"),
        poll_interval=0.1,
        batch_interval=0.1,
    ) as tracker:
        client = anthropic.Anthropic(api_key=anthropic_api_key)

        resp = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": "Say hi"}],
            max_tokens=20,
        )
        # Use helper; response_id will be auto-generated if missing
        resp = tracker.track_llm_usage(
            "anthropic", resp, response_id=getattr(resp, "id", None)
        )
        used_id = getattr(resp, "aicm_response_id", None) or getattr(resp, "id", None)
        _wait_for_cost_event(aicm_api_key, used_id)


def test_anthropic_track_streaming(anthropic_api_key, aicm_api_key, tmp_path):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    with Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        db_path=str(tmp_path / "anthropic_queue.db"),
        poll_interval=0.1,
        batch_interval=0.1,
    ) as tracker:
        client = anthropic.Anthropic(api_key=anthropic_api_key)

        response_id = None
        usage_payload = {}

        with client.messages.stream(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": "Say hi"}],
            max_tokens=20,
        ) as stream:
            for evt in stream:
                # Get response_id from the first event that has it
                if response_id is None:
                    response_id = getattr(evt, "id", None)

                # Extract usage from each event and accumulate
                from aicostmanager.usage_utils import get_streaming_usage_from_response

                up = get_streaming_usage_from_response(evt, "anthropic")
                if isinstance(up, dict) and up:
                    # Merge usage data (later events may have more complete info)
                    usage_payload.update(up)

        if not usage_payload:
            pytest.skip("No usage returned in streaming events; skipping")

        # Track usage; if no response_id from stream, track() will generate one and return it
        used_id = tracker.track(
            "anthropic",
            "anthropic::claude-3-5-sonnet-20241022",
            usage_payload,
            response_id=response_id,
        )

        final_id = response_id or used_id
        print(f"Using response_id: {final_id}")
        _wait_for_cost_event(aicm_api_key, final_id)
