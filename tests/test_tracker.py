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
    tracker.track("openai::gpt-5-mini", {"input_tokens": 1}, customer_key="abc")
    tracker.close()
    assert received
    record = received[0]["tracked"][0]
    assert record["service_key"] == "openai::gpt-5-mini"
    assert record["customer_key"] == "abc"


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


def test_tracker_anonymizes_usage_fields():
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
    tracker = Tracker(
        aicm_api_key="test",
        ini_path="ini",
        delivery=delivery,
        anonymize_fields=["keywords"],
    )

    usage = {
        "input_tokens": 1,
        "keywords": ["Mary", "O'Boyle"],
        "metadata": {"keywords": ["Nested"], "other": "value"},
    }

    tracker.track("openai::gpt-5-mini", usage)
    tracker.close()

    assert usage["keywords"] == ["Mary", "O'Boyle"]
    assert usage["metadata"]["keywords"] == ["Nested"]
    assert received
    payload = received[0]["tracked"][0]["payload"]
    assert payload["keywords"] == ["[REDACTED]", "[REDACTED]"]
    assert payload["metadata"]["keywords"] == ["[REDACTED]"]
    assert payload["input_tokens"] == 1


def test_tracker_anonymize_custom_callable():
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

    def anonymizer(value):
        if isinstance(value, list):
            return [f"anon-{idx}" for idx, _ in enumerate(value)]
        if isinstance(value, str):
            return "anon"
        return value

    usage = {
        "keywords": ["Mary", "O'Boyle"],
        "details": {"keywords": ["Nested"]},
    }

    tracker.track(
        "openai::gpt-5-mini",
        usage,
        anonymize_fields=["keywords"],
        anonymizer=anonymizer,
    )
    tracker.close()

    assert received
    payload = received[0]["tracked"][0]["payload"]
    assert payload["keywords"] == ["anon-0", "anon-1"]
    assert payload["details"]["keywords"] == ["anon-0"]
    assert usage["keywords"] == ["Mary", "O'Boyle"]


def test_tracker_update_anonymize_fields_between_calls():
    received: list[dict] = []

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
    tracker = Tracker(
        aicm_api_key="test",
        ini_path="ini",
        delivery=delivery,
        anonymize_fields=["keywords"],
    )

    first_usage = {"keywords": ["Mary", "O'Boyle"], "tags": ["first"]}
    tracker.track("openai::gpt-5-mini", first_usage)

    tracker.set_anonymize_fields(["tags"])
    second_usage = {"keywords": ["Alice"], "tags": ["second"]}
    tracker.track("openai::gpt-5-mini", second_usage)

    tracker.close()

    assert len(received) == 2

    first_payload = received[0]["tracked"][0]["payload"]
    assert first_payload["keywords"] == ["[REDACTED]", "[REDACTED]"]
    assert first_payload["tags"] == ["first"]

    second_payload = received[1]["tracked"][0]["payload"]
    assert second_payload["keywords"] == ["Alice"]
    assert second_payload["tags"] == ["[REDACTED]"]

    assert first_usage["keywords"] == ["Mary", "O'Boyle"]
    assert second_usage["tags"] == ["second"]
