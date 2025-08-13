import asyncio

import asyncio

from aicostmanager.tracker import Tracker


class DummyDelivery:
    def __init__(self):
        self.enqueued = []
        self.sent = []

    def enqueue(self, payload):
        self.enqueued.append(payload)

    def deliver_now(self, payload):
        self.sent.append(payload)
        return {"ok": True}

    async def deliver_now_async(self, payload):
        self.sent.append(payload)
        return {"ok": True}


def test_tracker_enqueue():
    delivery = DummyDelivery()
    tracker = Tracker(delivery=delivery)
    tracker.track("openai", "gpt-5-mini", {"input_tokens": 1})
    assert delivery.enqueued
    record = delivery.enqueued[0]
    assert record["api_id"] == "openai"
    assert record["service_key"] == "gpt-5-mini"
    assert "payload" in record


def test_tracker_sync_delivery():
    delivery = DummyDelivery()
    tracker = Tracker(delivery=delivery)
    resp = tracker.sync_track("openai", "gpt-5-mini", {"input_tokens": 1})
    assert delivery.sent
    assert resp["ok"]


def test_tracker_async_delivery():
    delivery = DummyDelivery()
    tracker = Tracker(delivery=delivery)

    async def run():
        resp = await tracker.sync_track_async("openai", "gpt-5-mini", {"input_tokens": 1})
        return resp

    resp = asyncio.run(run())
    assert delivery.sent
    assert resp["ok"]
