import json
import asyncio

from aicostmanager.tracker import Tracker
from aicostmanager.ini_manager import IniManager


class Resp:
    def __init__(self, usage, model):
        self.usage = usage
        self.model = model


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

    resp = Resp({"input_tokens": 1}, "gpt-5-mini")
    out = tracker.track_llm_usage("openai_chat", resp, client_customer_key="abc")
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
        resp.model = "gpt-4"
        out = await tracker.track_llm_usage_async("openai_chat", resp)
        assert out is resp

    asyncio.run(run())
    tracker.close()

    record = delivery.records[0]
    assert record["payload"] == {"input_tokens": 2}
    assert record["service_key"] == "gpt-4"


def test_track_llm_stream_usage():
    delivery = DummyDelivery()
    tracker = Tracker(delivery=delivery, ini_manager=IniManager("ini"))

    class Chunk:
        def __init__(self, usage=None):
            self.usage = usage

    class Stream(list):
        def __init__(self, chunks, model):
            super().__init__(chunks)
            self.model = model

    chunks = Stream([Chunk(), Chunk({"input_tokens": 3})], model="gpt-5-mini")
    events = list(tracker.track_llm_stream_usage("openai_chat", chunks))
    assert events == chunks
    tracker.close()

    record = delivery.records[0]
    assert record["payload"] == {"input_tokens": 3}
    assert record["service_key"] == "gpt-5-mini"


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
        gen = stream()
        gen.model = "gpt-5-mini"
        async for _ in tracker.track_llm_stream_usage_async("openai_chat", gen):
            pass

    asyncio.run(run())
    tracker.close()

    record = delivery.records[0]
    assert record["payload"] == {"input_tokens": 4}
    assert record["service_key"] == "gpt-5-mini"
