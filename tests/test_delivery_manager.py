import json
import time

import httpx

from aicostmanager import Tracker, DeliveryType


def test_tracker_default_immediate_delivery():
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    tracker = Tracker(aicm_api_key="test", transport=transport)
    tracker.track("openai", "gpt-5-mini", {"input_tokens": 1})
    assert received and received[0]["tracked"][0]["api_id"] == "openai"
    tracker.close()


def test_tracker_mem_queue_delivery():
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    tracker = Tracker(
        delivery_type=DeliveryType.MEM_QUEUE,
        aicm_api_key="test",
        transport=transport,
        batch_interval=0.1,
    )
    tracker.track("openai", "gpt-5-mini", {"input_tokens": 1})
    for _ in range(20):
        if received:
            break
        time.sleep(0.1)
    tracker.close()
    assert received


def test_tracker_persistent_queue_delivery(tmp_path):
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    db_path = tmp_path / "queue.db"
    tracker = Tracker(
        delivery_type=DeliveryType.PERSISTENT_QUEUE,
        aicm_api_key="test",
        db_path=str(db_path),
        transport=transport,
        poll_interval=0.1,
    )
    tracker.track("openai", "gpt-5-mini", {"input_tokens": 1})
    for _ in range(20):
        if received:
            break
        time.sleep(0.1)
    tracker.close()
    assert received


def test_immediate_delivery_retries():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(500, json={"ok": False})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    tracker = Tracker(aicm_api_key="test", transport=transport)
    tracker.track("openai", "gpt-5-mini", {"input_tokens": 1})
    tracker.close()
    assert attempts["count"] == 3


def test_immediate_delivery_does_not_retry_client_error():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(400, json={"ok": False})

    transport = httpx.MockTransport(handler)
    tracker = Tracker(aicm_api_key="test", transport=transport)
    try:
        tracker.track("openai", "gpt-5-mini", {"input_tokens": 1})
    except httpx.HTTPStatusError:
        pass
    tracker.close()
    assert attempts["count"] == 1
