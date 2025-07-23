"""Background delivery helpers for ``CostManager``.

This module provides a simple thread based queue that batches payloads
and retries failed requests using ``tenacity``.  A single global queue
is shared across all ``CostManager`` instances to avoid the overhead of
creating a new worker per wrapper.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Optional

from tenacity import Retrying, stop_after_attempt, wait_exponential_jitter

from .client import CostManagerClient


_global_delivery: "ResilientDelivery" | None = None

def get_global_delivery(
    client: CostManagerClient,
    *,
    max_retries: int = 5,
    queue_size: int = 1000,
    endpoint: str = "/track-usage",
    timeout: float = 10.0,
) -> "ResilientDelivery":
    """Return the shared delivery queue initialised with ``client``.

    The first caller creates the queue which is then reused by all
    subsequent ``CostManager`` instances.  The worker thread is started on
    creation.
    """
    global _global_delivery
    if _global_delivery is None:
        api_root = client.api_root
        _global_delivery = ResilientDelivery(
            client.session,
            api_root,
            endpoint=endpoint,
            max_retries=max_retries,
            queue_size=queue_size,
            timeout=timeout,
        )
        _global_delivery.start()
    else:
        # Ensure the worker is actually running.  Tests may stop the
        # singleton leaving the object assigned but the thread stopped.
        thread = getattr(_global_delivery, "_thread", None)
        if thread is None or not thread.is_alive():
            try:
                # ``stop`` is idempotent so it is safe to call even if not running
                _global_delivery.stop()
            except Exception:  # pragma: no cover - defensive
                pass
            _global_delivery.start()
    return _global_delivery


def get_global_delivery_health() -> Optional[dict[str, Any]]:
    """Return health information for the global queue if initialised."""
    if _global_delivery is None:
        return None
    return _global_delivery.get_health_info()


class ResilientDelivery:
    """Thread based delivery queue with retry logic."""

    def __init__(
        self,
        session: Any,
        api_root: str,
        *,
        endpoint: str = "/track-usage",
        max_retries: int = 5,
        queue_size: int = 1000,
        timeout: float = 10.0,
    ) -> None:
        self.session = session
        self.api_root = api_root.rstrip("/")
        self.endpoint = endpoint
        self.max_retries = max_retries
        self.timeout = timeout
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=queue_size)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._total_sent = 0
        self._total_failed = 0
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start the background worker if not already running."""
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop the worker and wait for queued items to be processed."""
        if self._thread is None:
            return
        self._stop.set()
        self._queue.put({})  # sentinel
        self._thread.join()
        self._thread = None

    def deliver(self, payload: dict[str, Any]) -> None:
        """Queue ``payload`` for delivery without blocking."""
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            logging.warning("Delivery queue full - dropping payload")

    # ------------------------------------------------------------------
    # Worker implementation
    # ------------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            item = self._queue.get()
            if self._stop.is_set():
                self._queue.task_done()
                break
            batch = [item]
            while True:
                try:
                    nxt = self._queue.get_nowait()
                    batch.append(nxt)
                except queue.Empty:
                    break
            try:
                payload = {"usage_records": []}
                for p in batch:
                    payload["usage_records"].extend(p.get("usage_records", []))
                self._send_with_retry(payload)
            finally:
                for _ in batch:
                    self._queue.task_done()

    def _send_with_retry(self, payload: dict[str, Any]) -> None:
        retry = Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=30),
            reraise=True,
        )
        try:
            for attempt in retry:
                with attempt:
                    response = self.session.post(
                        f"{self.api_root}{self.endpoint}",
                        json=payload,
                        timeout=self.timeout,
                    )
                    if hasattr(response, "raise_for_status"):
                        response.raise_for_status()
            self._total_sent += 1
        except Exception as exc:  # pragma: no cover - network failure
            logging.error("Failed to deliver payload after retries: %s", exc)
            self._total_failed += 1
            self._last_error = str(exc)

    # ------------------------------------------------------------------
    # Health helpers
    # ------------------------------------------------------------------
    def get_health_info(self) -> dict[str, Any]:
        """Return current queue metrics for debugging."""
        return {
            "worker_alive": self._thread is not None and self._thread.is_alive(),
            "queue_size": self._queue.qsize(),
            "queue_utilization": self._queue.qsize() / self._queue.maxsize,
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "last_error": self._last_error,
        }
