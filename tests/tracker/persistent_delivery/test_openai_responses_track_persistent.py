import json
import os
import time
import urllib.request
import uuid

import pytest

openai = pytest.importorskip("openai")

from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager
from aicostmanager.tracker import Tracker
from aicostmanager.usage_utils import extract_usage

BASE_URL = "http://127.0.0.1:8001"


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


def _make_client(api_key: str):
    return openai.OpenAI(api_key=api_key)


def test_openai_responses_track_non_streaming(aicm_api_key):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")
    ini = IniManager("ini")
    dconfig = DeliveryConfig(
        ini_manager=ini, aicm_api_key=aicm_api_key, aicm_api_base=BASE_URL
    )
    delivery = create_delivery(
        DeliveryType.PERSISTENT_QUEUE, dconfig, poll_interval=0.1, batch_interval=0.1
    )
    with Tracker(
        aicm_api_key=aicm_api_key, ini_path=ini.ini_path, delivery=delivery
    ) as tracker:
        client = _make_client(api_key)

        resp = client.responses.create(model="gpt-5-mini", input="Say hi")
        response_id = getattr(resp, "id", None)
        usage = extract_usage(resp)
        tracker.track(
            "openai_responses", "openai::gpt-5-mini", usage, response_id=response_id
        )
        _wait_for_cost_event(aicm_api_key, response_id)


def test_openai_responses_track_streaming(aicm_api_key):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set in .env file")
    ini = IniManager("ini2")
    dconfig = DeliveryConfig(
        ini_manager=ini, aicm_api_key=aicm_api_key, aicm_api_base=BASE_URL
    )
    delivery = create_delivery(
        DeliveryType.PERSISTENT_QUEUE, dconfig, poll_interval=0.1, batch_interval=0.1
    )
    with Tracker(
        aicm_api_key=aicm_api_key, ini_path=ini.ini_path, delivery=delivery
    ) as tracker:
        client = _make_client(api_key)

        response_id = None
        usage_payload = {}

        stream = client.responses.create(
            model="gpt-5-mini", input="Say hi", stream=True
        )

        # Process streaming events to accumulate usage data
        for evt in stream:
            # Get response_id from the first event that has it
            if response_id is None:
                response_id = getattr(evt, "id", None)

            # Extract usage from each event and accumulate
            from aicostmanager.usage_utils import get_streaming_usage_from_response

            up = get_streaming_usage_from_response(evt, "openai_responses")
            if isinstance(up, dict) and up:
                # Merge usage data (later events may have more complete info)
                usage_payload.update(up)

        if not usage_payload:
            pytest.skip("No usage returned in streaming events; skipping")

        # Track the usage and get the actual response_id that was used (auto-generate if missing)
        used_id = tracker.track(
            "openai_responses",
            "openai::gpt-5-mini",
            usage_payload,
            response_id=response_id,
        )

        final_id = response_id or used_id
        print(f"Using response_id: {final_id}")
        _wait_for_cost_event(aicm_api_key, final_id)
