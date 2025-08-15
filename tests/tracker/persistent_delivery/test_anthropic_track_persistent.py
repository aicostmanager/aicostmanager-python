import json
import os
import threading
import time
import urllib.request
import uuid

import pytest

anthropic = pytest.importorskip("anthropic")

from aicostmanager.persistent_delivery import PersistentDelivery
from aicostmanager.tracker import Tracker
from aicostmanager.usage_utils import extract_usage

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
    tracker.track(
        "anthropic",
        "anthropic::claude-3-5-sonnet-20241022",
        usage,
        response_id=response_id,
    )
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

    # Track the usage and get the actual response_id that was used
    tracker.track(
        "anthropic",
        "anthropic::claude-3-5-sonnet-20241022",
        usage_payload,
        response_id=response_id,
    )

    # If no response_id was provided, we need to get it from the persistent delivery
    # The persistent delivery generates its own ID when none is provided
    if response_id is None:
        # Temporarily stop the worker thread to prevent it from processing our message
        delivery._stop_event.set()
        delivery._worker.join(timeout=1.0)

        # Query the database to get the response_id
        import sqlite3

        conn = sqlite3.connect(str(tmp_path / "anthropic_queue.db"))

        # First, let's see what's in the queue
        cursor = conn.execute("SELECT id, payload FROM queue")
        rows = cursor.fetchall()
        print(f"Queue contents: {len(rows)} rows")
        for row in rows:
            print(f"  Row {row[0]}: {row[1][:100]}...")

        # Now try to get the most recent payload
        cursor = conn.execute("SELECT payload FROM queue ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            payload_data = json.loads(row[0])
            print(f"Payload data: {payload_data}")
            # The local storage format has response_id directly in the payload
            if "response_id" in payload_data:
                response_id = payload_data["response_id"]
                print(f"Found response_id: {response_id}")
        else:
            print("No rows found in queue")
        conn.close()

        # If we still don't have a response_id, we can't proceed
        if response_id is None:
            pytest.fail("Failed to get response_id from persistent delivery")

        # Restart the worker thread
        delivery._stop_event.clear()
        delivery._worker = threading.Thread(target=delivery._run_worker, daemon=True)
        delivery._worker.start()

    print(f"Using response_id: {response_id}")
    _wait_for_cost_event(aicm_api_key, response_id)
    tracker.close()
