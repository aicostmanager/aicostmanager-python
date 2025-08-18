from __future__ import annotations

import logging
import os
import queue
import threading
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .persistent_delivery import PersistentDelivery


logger = logging.getLogger(__name__)


class DeliveryManager(ABC):
    """Abstract base class for tracker delivery mechanisms."""

    @abstractmethod
    def enqueue(self, payload: Dict[str, Any]) -> None:
        """Queue ``payload`` for background delivery."""

    def stop(self) -> None:  # pragma: no cover - default no-op
        """Shutdown any background resources."""
        return None


class DeliveryManagerType(str, Enum):
    """Available delivery manager implementations."""

    IMMEDIATE = "immediate"
    MEM_QUEUE = "mem_queue"
    PERSISTENT_QUEUE = "persistent_queue"


class ImmediateDeliveryManager(DeliveryManager):
    """Synchronous delivery using direct HTTP requests with retries."""

    def __init__(
        self,
        *,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = aicm_api_key or os.getenv("AICM_API_KEY")
        self.api_base = aicm_api_base or os.getenv(
            "AICM_API_BASE", "https://aicostmanager.com"
        )
        self.api_url = aicm_api_url or os.getenv("AICM_API_URL", "/api/v1")
        self.timeout = timeout
        self._transport = transport
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._endpoint = (
            self.api_base.rstrip("/") + self.api_url.rstrip("/") + "/track"
        )
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "aicostmanager-python",
        }

    def enqueue(self, payload: Dict[str, Any]) -> None:
        body = {"tracked": [payload]}

        def _retryable(exc: Exception) -> bool:
            if isinstance(exc, httpx.HTTPStatusError):
                return exc.response is None or exc.response.status_code >= 500
            return True

        for attempt in Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(),
            retry=retry_if_exception(_retryable),
        ):
            with attempt:
                resp = self._client.post(
                    self._endpoint, json=body, headers=self._headers
                )
                resp.raise_for_status()
                return None

    def stop(self) -> None:  # pragma: no cover - nothing to cleanup
        self._client.close()


class MemQueueDeliveryManager(DeliveryManager):
    """In-memory queue with background delivery similar to ``ResilientDelivery``."""

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
    ) -> None:
        self.api_key = aicm_api_key or os.getenv("AICM_API_KEY")
        self.api_base = aicm_api_base or os.getenv(
            "AICM_API_BASE", "https://aicostmanager.com"
        )
        self.api_url = aicm_api_url or os.getenv("AICM_API_URL", "/api/v1")
        self.timeout = timeout
        self.max_retries = max_retries
        self.batch_interval = batch_interval
        self.max_batch_size = max_batch_size
        self._transport = transport
        self._endpoint = (
            self.api_base.rstrip("/") + self.api_url.rstrip("/") + "/track"
        )
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "aicostmanager-python",
        }
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=queue_size)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # Worker thread ---------------------------------------------------
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
        # Drain remaining items
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
        body = {"tracked": payloads}
        for attempt in Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(),
        ):
            with attempt:
                resp = self._client.post(
                    self._endpoint, json=body, headers=self._headers
                )
                resp.raise_for_status()
                return resp
        raise RuntimeError("unreachable")

    # DeliveryManager interface --------------------------------------
    def enqueue(self, payload: Dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            logger.warning("Delivery queue full")


    def stop(self) -> None:
        self._stop.set()
        self._thread.join()


class PersistentQueueDeliveryManager(DeliveryManager):
    """Wrapper around :class:`PersistentDelivery` using the ``DeliveryManager`` interface."""

    def __init__(self, **kwargs: Any) -> None:
        self._delivery = PersistentDelivery(**kwargs)

    def enqueue(self, payload: Dict[str, Any]) -> None:
        self._delivery.enqueue(payload)

    def stop(self) -> None:
        self._delivery.stop()
