import json
import os
import time
import urllib.request
import uuid

import pytest

openai = pytest.importorskip("openai")
from aicostmanager.tracker import Tracker

BASE_URL = os.environ.get("AICM_API_BASE", "http://localhost:8001")


def _usage_to_payload(usage):
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return usage
    # Try common conversion methods used by OpenAI-compatible SDKs
    for attr in ("model_dump", "dict", "to_dict"):
        fn = getattr(usage, attr, None)
        if callable(fn):
            try:
                data = fn()
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
    return (
        usage  # Fallback; if not JSON-serializable, the request will surface the issue
    )


def _wait_for_enqueued(delivery, timeout: float = 1.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        stats = delivery.get_stats()
        if stats.get("queued", 0) > 0:
            return True
        # Check if already picked up by the worker but not yet flushed
        try:
            processing = delivery.list_messages("processing", 1)
        except Exception:
            processing = []
        if processing:
            return True
        time.sleep(0.01)
    return False


def _wait_for_empty(delivery, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        stats = delivery.get_stats()
        queued = stats.get("queued", 0)
        processing = stats.get("processing", 0)
        if queued == 0 and processing == 0:
            return True
        time.sleep(0.05)
    return False


def _wait_for_cost_event(aicm_api_key: str, response_id: str, timeout: int = 30):
    headers = {"Authorization": f"Bearer {aicm_api_key}"}
    deadline = time.time() + timeout
    last_data = None
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/api/v1/cost-events/{response_id}",
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.load(resp)
                    last_data = data
                    # Server may return a single object or a list of events
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
    # Enable verbose delivery logging to aid debugging of server requests
    os.environ["AICM_DELIVERY_LOG_BODIES"] = "true"
    tracker = Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    )
    client = maker(api_key)

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hi"}],
        max_completion_tokens=20,
    )
    response_id = getattr(resp, "id", None)
    usage_payload = _usage_to_payload(getattr(resp, "usage", None))
    tracker.track("openai_chat", service_key, usage_payload, response_id=response_id)
    assert _wait_for_enqueued(tracker.delivery, timeout=1.0), (
        "Usage record was not enqueued by PersistentDelivery"
    )
    health = tracker.delivery.health()
    assert health.get("worker_alive"), "PersistentDelivery worker thread is not alive"
    assert _wait_for_empty(tracker.delivery, timeout=10.0), (
        f"Queue did not flush; stats={tracker.delivery.get_stats()}"
    )
    _wait_for_cost_event(aicm_api_key, response_id)

    resp2 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hi again"}],
        max_completion_tokens=20,
    )
    response_id2 = getattr(resp2, "id", None)
    usage_payload2 = _usage_to_payload(getattr(resp2, "usage", None))
    delivery_resp = tracker.deliver_now(
        "openai_chat", service_key, usage_payload2, response_id=response_id2
    )
    assert delivery_resp.status_code in (200, 201)
    _wait_for_cost_event(aicm_api_key, response_id2)

    tracker.close()
