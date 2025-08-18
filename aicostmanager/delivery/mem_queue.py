from __future__ import annotations

import os
import queue
import threading
import time
from typing import Any, Dict, List, Optional

import httpx
from tenacity import Retrying, stop_after_attempt, wait_exponential_jitter

from .base import Delivery

_global_delivery: MemQueueDelivery | None = None


class MemQueueDelivery(Delivery):
    """In-memory queue with background delivery."""

    def __init__(
        self,
        *,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 5,
        queue_size: int = 1000,
        batch_interval: float = 0.5,
        max_batch_size: int = 100,
        transport: httpx.BaseTransport | None = None,
        endpoint: str = "/track",
        body_key: str = "tracked",
        log_file: str | None = None,
        log_level: str | None = None,
    ) -> None:
        super().__init__(log_file=log_file, log_level=log_level)
        self.api_key = aicm_api_key or os.getenv("AICM_API_KEY")
        self.api_base = aicm_api_base or os.getenv("AICM_API_BASE", "https://aicostmanager.com")
        self.api_url = aicm_api_url or os.getenv("AICM_API_URL", "/api/v1")
        self.timeout = timeout
        self.max_retries = max_retries
        self.batch_interval = batch_interval
        self.max_batch_size = max_batch_size
        self._transport = transport
        self._endpoint = self.api_base.rstrip("/") + self.api_url.rstrip("/") + endpoint
        self._body_key = body_key
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "aicostmanager-python",
        }
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=queue_size)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
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
        for attempt in Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(),
        ):
            with attempt:
                resp = self._client.post(self._endpoint, json=body, headers=self._headers)
                resp.raise_for_status()
                self._total_sent += len(payloads)
                return resp
        raise RuntimeError("unreachable")

    def enqueue(self, payload: Dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            self.logger.warning("Delivery queue full")
            self._total_failed += 1

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()

    def stats(self) -> Dict[str, Any]:
        return {
            "queued": self._queue.qsize(),
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
        }


def get_global_delivery(*, transport: httpx.BaseTransport | None = None, **kwargs: Any) -> MemQueueDelivery:
    global _global_delivery
    if _global_delivery is None:
        _global_delivery = MemQueueDelivery(transport=transport, **kwargs)
    return _global_delivery


def get_global_delivery_health() -> Dict[str, Any] | None:
    if _global_delivery is None:
        return None
    return _global_delivery.stats()
