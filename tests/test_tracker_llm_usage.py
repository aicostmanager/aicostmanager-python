import json
import asyncio

from aicostmanager.tracker import Tracker
from aicostmanager.ini_manager import IniManager


class Resp:
    def __init__(self, usage):
        self.usage = usage


class DummyDelivery:
    def __init__(self):
        self.records = []
        self.type = None

    def enqueue(self, record):
        self.records.append(record)

    def stop(self):
        pass


def test_track_llm_usage():
    delivery = DummyDelivery()
    tracker = Tracker(delivery=delivery, ini_manager=IniManager("ini"))

    resp = Resp({"input_tokens": 1})
    out = tracker.track_llm_usage("openai_chat", "gpt-5-mini", resp, client_customer_key="abc")
    assert out is resp
    tracker.close()

    record = delivery.records[0]
    assert record["payload"] == {"input_tokens": 1}
    assert record["api_id"] == "openai_chat"
    assert record["service_key"] == "gpt-5-mini"
    assert record["client_customer_key"] == "abc"


def test_track_llm_usage_async():
    delivery = DummyDelivery()
    tracker = Tracker(delivery=delivery, ini_manager=IniManager("ini"))

    class AResp:
        usage = {"input_tokens": 2}

    async def run():
        resp = AResp()
        out = await tracker.track_llm_usage_async("openai_chat", "gpt-4", resp)
        assert out is resp

    asyncio.run(run())
    tracker.close()

    record = delivery.records[0]
    assert record["payload"] == {"input_tokens": 2}


def test_track_llm_stream_usage():
    delivery = DummyDelivery()
    tracker = Tracker(delivery=delivery, ini_manager=IniManager("ini"))

    class Chunk:
        def __init__(self, usage=None):
            self.usage = usage

    chunks = [Chunk(), Chunk({"input_tokens": 3})]
    events = list(tracker.track_llm_stream_usage("openai_chat", "gpt-5-mini", chunks))
    assert events == chunks
    tracker.close()

    record = delivery.records[0]
    assert record["payload"] == {"input_tokens": 3}


def test_track_llm_stream_usage_async():
    delivery = DummyDelivery()
    tracker = Tracker(delivery=delivery, ini_manager=IniManager("ini"))

    class Chunk:
        def __init__(self, usage=None):
            self.usage = usage

    async def stream():
        for c in [Chunk(), Chunk({"input_tokens": 4})]:
            yield c

    async def run():
        async for _ in tracker.track_llm_stream_usage_async("openai_chat", "gpt-5-mini", stream()):
            pass

    asyncio.run(run())
    tracker.close()

    record = delivery.records[0]
    assert record["payload"] == {"input_tokens": 4}

