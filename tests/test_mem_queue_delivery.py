import json
import time

import httpx

from aicostmanager.delivery import DeliveryConfig, MemQueueDelivery
from aicostmanager.ini_manager import IniManager


def test_mem_queue_delivery_sends_and_tracks_stats(tmp_path):
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.read().decode()))
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
    cfg = DeliveryConfig(
        ini_manager=IniManager(str(tmp_path / "aicm.ini")),
        aicm_api_key="sk-test",
        aicm_api_base="https://example.com",
        aicm_api_url="",
        transport=transport,
    )
    delivery = MemQueueDelivery(
        cfg, batch_interval=0.01, max_batch_size=10, max_attempts=1
    )
    payload = {"foo": "bar"}
    delivery.enqueue(payload)

    for _ in range(100):
        if delivery.stats()["queued"] == 0:
            break
        time.sleep(0.02)
    delivery.stop()

    assert sent and sent[0]["tracked"][0] == payload
    stats = delivery.stats()
    assert stats["queued"] == 0
    assert stats["total_sent"] == 1
    assert stats["total_failed"] == 0
