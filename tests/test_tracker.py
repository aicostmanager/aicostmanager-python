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

    async def deliver_now_async(self, payload):
        self.sent.append(payload)


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
    tracker.track_sync("openai", "gpt-5-mini", {"input_tokens": 1})
    assert delivery.sent


def test_tracker_async_delivery():
    delivery = DummyDelivery()
    tracker = Tracker(delivery=delivery)

    async def run():
        await tracker.track_sync_async("openai", "gpt-5-mini", {"input_tokens": 1})

    asyncio.run(run())
    assert delivery.sent
