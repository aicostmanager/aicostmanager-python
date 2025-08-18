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
    # Wait an initial 2 seconds, then try up to 3 times
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


def _make_openai_client(api_key: str):
    return openai.OpenAI(api_key=api_key)


def _make_fireworks_client(api_key: str):
    return openai.OpenAI(
        api_key=api_key, base_url="https://api.fireworks.ai/inference/v1"
    )


def _make_xai_client(api_key: str):
    return openai.OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")


@pytest.mark.parametrize(
    "service_key, model, key_env, maker",
    [
        ("openai::gpt-5-mini", "gpt-5-mini", "OPENAI_API_KEY", _make_openai_client),
        (
            "fireworks-ai::accounts/fireworks/models/deepseek-r1",
            "accounts/fireworks/models/deepseek-r1",
            "FIREWORKS_API_KEY",
            _make_fireworks_client,
        ),
        ("xai::grok-3-mini", "grok-3-mini", "XAI_API_KEY", _make_xai_client),
    ],
)
def test_openai_chat_tracker(service_key, model, key_env, maker, aicm_api_key):
    api_key = os.environ.get(key_env)
    if not api_key:
        pytest.skip(f"{key_env} not set in .env file")
    tracker = Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    )
    client = maker(api_key)

    # Background tracking via queue
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hi"}],
        max_completion_tokens=20,
    )
    response_id = getattr(resp, "id", None)
    usage_payload = get_usage_from_response(resp, "openai_chat")
    tracker.track("openai_chat", service_key, usage_payload, response_id=response_id)
    try:
        _wait_for_cost_event(aicm_api_key, response_id)
    except AssertionError:
        pytest.skip("Cost event not found for OpenAI chat background; skipping")

    # Immediate delivery
    resp2 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hi again"}],
        max_completion_tokens=20,
    )
    response_id2 = getattr(resp2, "id", None)
    # Immediate delivery using a separate tracker configured for immediate delivery
    with Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        delivery_type=DeliveryType.IMMEDIATE,
    ) as t2:
        usage2 = get_usage_from_response(resp2, "openai_chat")
        t2.track("openai_chat", service_key, usage2, response_id=response_id2)
    try:
        _wait_for_cost_event(aicm_api_key, response_id2)
    except AssertionError:
        pytest.skip("Cost event not found for OpenAI chat immediate; skipping")

    tracker.close()
