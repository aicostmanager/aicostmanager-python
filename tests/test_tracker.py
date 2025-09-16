import asyncio
import json

import httpx

from aicostmanager import Tracker
from aicostmanager.delivery import DeliveryConfig, DeliveryType, create_delivery
from aicostmanager.ini_manager import IniManager


def test_tracker_builds_record():
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.read().decode()))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "response_id": "r1",
                        "cost_events": [{"vendor_id": "v", "service_id": "s"}],
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
    tracker.track("openai::gpt-5-mini", {"input_tokens": 1}, client_customer_key="abc")
    tracker.close()
    assert received
    record = received[0]["tracked"][0]
    assert record["service_key"] == "openai::gpt-5-mini"
    assert record["client_customer_key"] == "abc"


def test_tracker_track_async():
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.read().decode()))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "response_id": "r1",
                        "cost_events": [{"vendor_id": "v", "service_id": "s"}],
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

    async def run():
        await tracker.track_async("openai::gpt-5-mini", {"input_tokens": 1})

    asyncio.run(run())
    tracker.close()
    assert received
