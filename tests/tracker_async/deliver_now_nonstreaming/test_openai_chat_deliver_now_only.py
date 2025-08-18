import asyncio
import json
import os
import time
import urllib.request
import uuid

import pytest

from aicostmanager.delivery import DeliveryType
from aicostmanager.tracker import Tracker
from aicostmanager.usage_utils import get_usage_from_response

openai = pytest.importorskip("openai")

BASE_URL = "http://127.0.0.1:8001"


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


def _make_openai_client(api_key: str):
    return openai.OpenAI(api_key=api_key)


@pytest.mark.parametrize(
    "service_key, model, key_env, maker",
    [("openai::gpt-5-mini", "gpt-5-mini", "OPENAI_API_KEY", _make_openai_client)],
)
def test_openai_chat_deliver_now_only(service_key, model, key_env, maker, aicm_api_key):
    api_key = os.environ.get(key_env)
    if not api_key:
        pytest.skip(f"{key_env} not set in .env file")
    os.environ["AICM_DELIVERY_LOG_BODIES"] = "true"
    with Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
        delivery_type=DeliveryType.IMMEDIATE,
    ) as tracker:
        client = maker(api_key)

        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say hi (deliver_now_only)"}],
            max_completion_tokens=20,
        )
        response_id = getattr(resp, "id", None)
        usage_payload = get_usage_from_response(resp, "openai_chat")

        asyncio.run(
            tracker.track_async(
                "openai_chat", service_key, usage_payload, response_id=response_id
            )
        )
        _wait_for_cost_event(aicm_api_key, response_id)
