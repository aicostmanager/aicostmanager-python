import asyncio
import json

import httpx

from aicostmanager import Tracker, TrackerConfig
from aicostmanager.ini_manager import IniManager


def test_tracker_builds_record():
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    cfg = TrackerConfig.from_env(
        aicm_api_key="test", transport=transport, ini_manager=IniManager("ini")
    )
    tracker = Tracker(cfg)
    tracker.track("openai", "gpt-5-mini", {"input_tokens": 1}, client_customer_key="abc")
    tracker.close()
    assert received
    record = received[0]["tracked"][0]
    assert record["api_id"] == "openai"
    assert record["service_key"] == "gpt-5-mini"
    assert record["client_customer_key"] == "abc"


def test_tracker_track_async():
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    cfg = TrackerConfig.from_env(
        aicm_api_key="test", transport=transport, ini_manager=IniManager("ini")
    )
    tracker = Tracker(cfg)

    async def run():
        await tracker.track_async("openai", "gpt-5-mini", {"input_tokens": 1})

    asyncio.run(run())
    tracker.close()
    assert received

