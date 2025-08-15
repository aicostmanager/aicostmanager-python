import json
import os
import time
import urllib.request
import uuid

import pytest

from aicostmanager.tracker import Tracker
from aicostmanager.usage_utils import get_streaming_usage_from_response

anthropic = pytest.importorskip("anthropic")

BASE_URL = os.environ.get("AICM_API_BASE", "http://127.0.0.1:8001")


def _wait_for_cost_event(aicm_api_key: str, response_id: str):
    headers = {"Authorization": f"Bearer {aicm_api_key}"}
    time.sleep(5)
    last_data = None
    for _ in range(3):
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/api/v1/cost-events/{response_id}", headers=headers
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.load(resp)
                    last_data = data
                    if isinstance(data, list):
                        if data:
                            evt = data[0]
                            evt_id = evt.get("event_id") or evt.get("uuid")
                            if evt_id:
                                uuid.UUID(str(evt_id))
                                return data
                    else:
                        event_id = data.get("event_id") or data.get(
                            "cost_event", {}
                        ).get("event_id")
                        if event_id:
                            uuid.UUID(str(event_id))
                            return data
        except Exception:
            pass
        time.sleep(1)
    raise AssertionError(
        f"cost event for {response_id} not found; last_data={last_data} base_url={BASE_URL}"
    )


@pytest.mark.parametrize(
    "service_key, model",
    [
        ("anthropic::claude-sonnet-4-20250514", "claude-sonnet-4-20250514"),
        ("anthropic::claude-sonnet-4-0", "claude-sonnet-4-20250514"),
    ],
)
def test_anthropic_deliver_now_streaming(
    service_key, model, anthropic_api_key, aicm_api_key
):
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in .env file")
    os.environ["AICM_DELIVERY_LOG_BODIES"] = "true"
    with Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    ) as tracker:
        client = anthropic.Anthropic(api_key=anthropic_api_key)

        response_id = uuid.uuid4().hex
        usage_payload = {}

        print("anthropic response_id:", response_id)
        stream = client.messages.stream(
            model=model,
            messages=[{"role": "user", "content": "Say hi (deliver_now_streaming)"}],
            max_tokens=32,
        )
        with stream as s:
            for evt in s:
                try:
                    etype = getattr(evt, "type", type(evt))
                    print("anthropic event type:", etype)
                    if hasattr(evt, "message") and hasattr(evt.message, "usage"):
                        print("anthropic event message.usage:", evt.message.usage)
                    if hasattr(evt, "usage"):
                        print("anthropic event usage:", evt.usage)
                except Exception:
                    pass
                up = get_streaming_usage_from_response(evt, "anthropic")
                if isinstance(up, dict) and up:
                    print("anthropic usage chunk:", json.dumps(up, default=str))
                    usage_payload = up

        if not usage_payload:
            pytest.skip("No usage returned in streaming events; skipping")

        print("anthropic final usage payload:", json.dumps(usage_payload, default=str))
        delivery_resp = tracker.deliver_now(
            "anthropic", service_key, usage_payload, response_id=response_id
        )
        assert delivery_resp.status_code in (200, 201)

        _wait_for_cost_event(aicm_api_key, response_id)
