import json
import time
import urllib.request
import uuid

import pytest

genai = pytest.importorskip("google.genai")

from aicostmanager.delivery import DeliveryType
from aicostmanager.tracker import Tracker

BASE_URL = "http://127.0.0.1:8001"


def _to_dict(obj, *, by_alias: bool = False):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    for attr in ("model_dump", "dict", "to_dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                if attr == "model_dump":
                    try:
                        data = fn(by_alias=by_alias)
                    except TypeError:
                        data = fn()
                else:
                    data = fn()
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
    return obj


def _extract_usage_payload(resp) -> dict:
    for attr in ("usageMetadata", "usage_metadata", "usage"):
        val = getattr(resp, attr, None)
        if val is not None:
            data = _to_dict(val, by_alias=True)
            if isinstance(data, dict) and data:
                return data
    try:
        data = _to_dict(resp, by_alias=True)
        for key in ("usageMetadata", "usage_metadata", "usage"):
            if isinstance(data, dict) and key in data:
                return _to_dict(data.get(key), by_alias=True)

        # Heuristic nested search
        def find_usage(d: dict):
            for k, v in d.items():
                if isinstance(v, dict):
                    keys = set(v.keys())
                    if {
                        "promptTokenCount",
                        "candidatesTokenCount",
                        "totalTokenCount",
                    } & keys or {
                        "prompt_token_count",
                        "candidates_token_count",
                        "total_token_count",
                    } & keys:
                        return v
                    found = find_usage(v)
                    if found is not None:
                        return found
            return None

        if isinstance(data, dict):
            found = find_usage(data)
            if found is not None:
                return _to_dict(found, by_alias=True)
    except Exception:
        pass
    return {}


def _normalize_gemini_usage(usage: dict) -> dict:
    if not isinstance(usage, dict):
        return {}
    key_map = {
        "prompt_token_count": "promptTokenCount",
        "candidates_token_count": "candidatesTokenCount",
        "total_token_count": "totalTokenCount",
    }
    normalized: dict = {}
    for k, v in usage.items():
        if k in ("promptTokenCount", "candidatesTokenCount", "totalTokenCount"):
            normalized[k] = v
        elif k in key_map:
            normalized[key_map[k]] = v
    allowed = {"promptTokenCount", "candidatesTokenCount", "totalTokenCount"}
    return {k: v for k, v in normalized.items() if k in allowed}


def _wait_for_cost_event(aicm_api_key: str, response_id: str, timeout: int = 30):
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


@pytest.mark.parametrize(
    "service_key, model",
    [("google::gemini-2.5-flash", "gemini-2.5-flash")],
)
def test_gemini_tracker(service_key, model, google_api_key, aicm_api_key):
    if not google_api_key:
        pytest.skip("GOOGLE_API_KEY not set in .env file")
    tracker = Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        poll_interval=0.1,
        batch_interval=0.1,
    )
    client = genai.Client(api_key=google_api_key)

    # Background tracking via queue
    resp = client.models.generate_content(model=model, contents="Say hi")
    # Try helper path by feeding usage via track(); if no id, generate and track
    response_id = getattr(resp, "id", None) or getattr(resp, "response_id", None)
    usage_payload = _extract_usage_payload(resp)
    usage_payload = _normalize_gemini_usage(usage_payload)
    used_id = tracker.track(
        "gemini", service_key, usage_payload, response_id=response_id
    )
    final_id = response_id or used_id
    _wait_for_cost_event(aicm_api_key, final_id)

    # Immediate delivery
    resp2 = client.models.generate_content(model=model, contents="Say hi again")
    response_id2 = getattr(resp2, "id", None) or getattr(resp2, "response_id", None)
    with Tracker(
        aicm_api_key=aicm_api_key,
        aicm_api_base=BASE_URL,
        delivery_type=DeliveryType.IMMEDIATE,
    ) as t2:
        # Use extracted usage if available, else minimal payload
        usage2 = _normalize_gemini_usage(_extract_usage_payload(resp2)) or {
            "totalTokenCount": 1
        }
        used2 = t2.track("gemini", service_key, usage2, response_id=response_id2)
    _wait_for_cost_event(aicm_api_key, response_id2 or used2)

    tracker.close()
