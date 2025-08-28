import json
import json
import time

import httpx
import pytest

from aicostmanager import Tracker
from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager


def test_tracker_default_immediate_delivery():
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={})
        received.append(json.loads(request.read().decode()))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "response_id": "evt1",
                        "cost_events": [
                            {
                                "vendor_id": "openai",
                                "service_id": "gpt-5-mini",
                                "cost_unit_id": "token",
                                "quantity": "1",
                                "cost_per_unit": "0.0000020",
                                "cost": "0.000002",
                            }
                        ],
                    }
                ],
                "triggered_limits": {},
            },
        )

    transport = httpx.MockTransport(handler)
    ini = IniManager("ini")
    dconfig = DeliveryConfig(ini_manager=ini, aicm_api_key="test", transport=transport)
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig)
    tracker = Tracker(aicm_api_key="test", ini_path="ini", delivery=delivery)
    tracker.track("openai", "gpt-5-mini", {"input_tokens": 1})
    assert received and received[0]["tracked"][0]["api_id"] == "openai"
    tracker.close()


def test_tracker_persistent_queue_delivery(tmp_path):
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={})
        received.append(json.loads(request.read().decode()))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    db_path = tmp_path / "queue.db"
    ini = IniManager(str(tmp_path / "ini"))
    dconfig = DeliveryConfig(
        ini_manager=ini,
        aicm_api_key="test",
        transport=transport,
    )
    delivery = create_delivery(
        DeliveryType.PERSISTENT_QUEUE,
        dconfig,
        db_path=str(db_path),
        poll_interval=0.1,
    )
    tracker = Tracker(
        aicm_api_key="test", ini_path=str(tmp_path / "ini"), delivery=delivery
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
        if request.method == "GET":
            return httpx.Response(200, json={})
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(500, json={"ok": False})
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "response_id": "evt1",
                        "cost_events": [
                            {
                                "vendor_id": "openai",
                                "service_id": "gpt-5-mini",
                                "cost_unit_id": "token",
                                "quantity": "1",
                                "cost_per_unit": "0.0000020",
                                "cost": "0.000002",
                            }
                        ],
                    }
                ],
                "triggered_limits": {},
            },
        )

    transport = httpx.MockTransport(handler)
    ini = IniManager("ini")
    dconfig = DeliveryConfig(ini_manager=ini, aicm_api_key="test", transport=transport)
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig)
    tracker = Tracker(aicm_api_key="test", ini_path="ini", delivery=delivery)
    tracker.track("openai", "gpt-5-mini", {"input_tokens": 1})
    tracker.close()
    assert attempts["count"] == 3


def test_immediate_delivery_does_not_retry_client_error():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={})
        attempts["count"] += 1
        return httpx.Response(400, json={"ok": False})

    transport = httpx.MockTransport(handler)
    ini = IniManager("ini")
    dconfig = DeliveryConfig(ini_manager=ini, aicm_api_key="test", transport=transport)
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig)
    tracker = Tracker(aicm_api_key="test", ini_path="ini", delivery=delivery)
    try:
        tracker.track("openai", "gpt-5-mini", {"input_tokens": 1})
    except httpx.HTTPStatusError:
        pass
    tracker.close()
    assert attempts["count"] == 1


def test_immediate_delivery_raises_on_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={})
        return httpx.Response(500, json={})

    transport = httpx.MockTransport(handler)
    ini = IniManager("ini")
    dconfig = DeliveryConfig(ini_manager=ini, aicm_api_key="test", transport=transport)
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig, raise_on_error=True)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            delivery.enqueue({"api_id": "openai"})
    finally:
        delivery.stop()


def test_immediate_delivery_continues_on_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={})
        return httpx.Response(500, json={})

    transport = httpx.MockTransport(handler)
    ini = IniManager("ini")
    dconfig = DeliveryConfig(ini_manager=ini, aicm_api_key="test", transport=transport)
    delivery = create_delivery(DeliveryType.IMMEDIATE, dconfig, raise_on_error=False)
    try:
        result = delivery.enqueue({"api_id": "openai"})
        assert "error" in result
    finally:
        delivery.stop()
