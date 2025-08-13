import os
import tempfile
import time

import httpx
import json

from aicostmanager.persistent_delivery import PersistentDelivery


def test_deliver_now_and_enqueue():
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        # httpx.Request no longer exposes a ``json`` method in recent versions,
        # so parse the body manually for compatibility.
        received.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "queue.db")
        delivery = PersistentDelivery(
            aicm_api_key="test",
            db_path=db_path,
            transport=transport,
            poll_interval=0.1,
        )

        payload = {"api_id": "openai", "service_key": "svc", "payload": {}}

        # Immediate send
        resp = delivery.deliver_now(payload)
        assert resp.json()["ok"]
        assert received[0]["tracked"][0]["api_id"] == "openai"

        # Queued send
        delivery.enqueue(payload)
        # Wait for worker
        for _ in range(20):
            if delivery.get_stats().get("queued", 0) == 0:
                break
            time.sleep(0.1)

        # second request should also wrap in tracked list
        assert any(r["tracked"][0]["service_key"] == "svc" for r in received)
        health = delivery.health()
        assert "worker_alive" in health
        delivery.stop()


def test_batch_delivery_groups_messages():
    batches = []

    def handler(request: httpx.Request) -> httpx.Response:
        batches.append(json.loads(request.content.decode())["tracked"])
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "queue.db")
        delivery = PersistentDelivery(
            aicm_api_key="test",
            db_path=db_path,
            transport=transport,
            poll_interval=0.1,
        )

        payload = {"api_id": "openai", "service_key": "svc", "payload": {}}
        for _ in range(120):
            delivery.enqueue(payload)

        # Wait for worker to drain
        for _ in range(50):
            if delivery.get_stats().get("queued", 0) == 0:
                break
            time.sleep(0.1)

        delivery.stop()

        assert len(batches) == 2
        assert len(batches[0]) == 100
        assert len(batches[1]) == 20
