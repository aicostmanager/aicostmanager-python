from __future__ import annotations

import queue
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

from .base import Delivery
from ..ini_manager import IniManager


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
        ini_manager: IniManager | None = None,
        log_file: str | None = None,
        log_level: str | None = None,
    ) -> None:
        super().__init__(
            ini_manager=ini_manager,
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            timeout=timeout,
            transport=transport,
            endpoint=endpoint,
            body_key=body_key,
            log_file=log_file,
            log_level=log_level,
        )
        self.max_retries = max_retries
        self.batch_interval = batch_interval
        self.max_batch_size = max_batch_size
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
        resp = self._post_with_retry(body, max_attempts=self.max_retries)
        self._total_sent += len(payloads)
        return resp

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
