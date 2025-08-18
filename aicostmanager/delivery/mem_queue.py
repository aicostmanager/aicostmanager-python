from __future__ import annotations

import queue
import time
from typing import Any, Dict, List

import httpx

from .base import DeliveryConfig, DeliveryType, QueueDelivery


class MemQueueDelivery(QueueDelivery):
    """In-memory queue with background delivery."""

    type = DeliveryType.MEM_QUEUE

    def __init__(
        self,
        config: DeliveryConfig,
        *,
        queue_size: int = 1000,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=queue_size)
        self._total_sent = 0
        self._total_failed = 0

    def _run(self) -> None:
        batch: List[Dict[str, Any]] = []
        last_flush = time.time()
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=self.batch_interval)
                batch.append(item)
                if len(batch) >= self.max_batch_size:
                    self._send_batch(batch)
                    batch = []
                    last_flush = time.time()
            except queue.Empty:
                pass
            if batch and (time.time() - last_flush) >= self.batch_interval:
                self._send_batch(batch)
                batch = []
                last_flush = time.time()
        while True:
            try:
                batch.append(self._queue.get_nowait())
                if len(batch) >= self.max_batch_size:
                    self._send_batch(batch)
                    batch = []
            except queue.Empty:
                break
        if batch:
            self._send_batch(batch)
        self._client.close()

    def _send_batch(self, payloads: List[Dict[str, Any]]) -> httpx.Response:
        body = {self._body_key: payloads}
        resp = self._post_with_retry(body, max_attempts=self.max_retries)
        self._total_sent += len(payloads)
        return resp

    def enqueue(self, payload: Dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            self.logger.warning("Delivery queue full")
            self._total_failed += 1

    def stats(self) -> Dict[str, Any]:
        return {
            "queued": self._queue.qsize(),
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
        }
