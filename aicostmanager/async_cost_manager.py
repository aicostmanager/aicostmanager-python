"""Asynchronous variant of :class:`CostManager`."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional, List

from .client import CostManagerClient, AsyncCostManagerClient
from .config_manager import CostManagerConfig, Config
from .universal_extractor import UniversalExtractor
from .cost_manager import _AsyncStreamIterator


class AsyncResilientDelivery:
    """Asyncio based delivery queue with retry logic."""

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
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_size)
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._total_sent = 0
        self._total_failed = 0
        self._last_error: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start the background worker if not already running."""
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the worker and wait for queued items to be processed."""
        if self._task is None:
            return
        self._stop.set()
        await self._queue.put({})  # sentinel
        await self._task
        self._task = None

    def deliver(self, payload: dict[str, Any]) -> None:
        """Queue ``payload`` for delivery without blocking."""
        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            logging.warning("Delivery queue full - dropping payload")

    # ------------------------------------------------------------------
    # Worker implementation
    # ------------------------------------------------------------------
    async def _run(self) -> None:
        while not self._stop.is_set():
            item = await self._queue.get()
            if self._stop.is_set():
                self._queue.task_done()
                break
            batch = [item]
            while True:
                try:
                    nxt = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                else:
                    batch.append(nxt)
            try:
                payload = {"usage_records": []}
                for p in batch:
                    payload["usage_records"].extend(p.get("usage_records", []))
                await self._send_with_retry(payload)
            finally:
                for _ in batch:
                    self._queue.task_done()

    async def _send_with_retry(self, payload: dict[str, Any]) -> None:
        from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential_jitter

        retry = AsyncRetrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=30),
            reraise=True,
        )
        try:
            async for attempt in retry:
                with attempt:
                    resp = await self.session.post(
                        f"{self.api_root}{self.endpoint}",
                        json=payload,
                        timeout=self.timeout,
                    )
                    if hasattr(resp, "raise_for_status"):
                        resp.raise_for_status()
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
            "worker_alive": self._task is not None and not self._task.done(),
            "queue_size": self._queue.qsize(),
            "queue_utilization": self._queue.qsize() / self._queue.maxsize,
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "last_error": self._last_error,
        }


class AsyncCostManager:
    """Wrap an async API client to facilitate usage tracking."""

    def __init__(
        self,
        client: Any,
        *,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        aicm_ini_path: Optional[str] = None,
        delivery: AsyncResilientDelivery | None = None,
        delivery_queue_size: int = 1000,
        delivery_max_retries: int = 5,
        delivery_timeout: float = 10.0,
    ) -> None:
        self.client = client
        # synchronous client used for configuration loading only
        cfg_client = CostManagerClient(
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
        )
        self.cm_client = AsyncCostManagerClient(
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
        )
        self.config_manager = CostManagerConfig(cfg_client)
        self.api_id = client.__class__.__name__.lower()
        self.configs: List[Config] = self.config_manager.get_config(self.api_id)
        cfg_client.close()
        self.extractor = UniversalExtractor(self.configs)
        self.tracked_payloads: list[dict[str, Any]] = []

        if delivery is not None:
            self.delivery = delivery
        else:
            self.delivery = AsyncResilientDelivery(
                self.cm_client.session,
                self.cm_client.api_root,
                max_retries=delivery_max_retries,
                queue_size=delivery_queue_size,
                timeout=delivery_timeout,
            )
        self.delivery.start()
    # ------------------------------------------------------------
    # attribute proxying
    # ------------------------------------------------------------
    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.client, name)

        if not callable(attr):
            return attr

        async def wrapper(*args, **kwargs):
            response = await attr(*args, **kwargs)
            if kwargs.get("stream") and hasattr(response, "__aiter__"):
                return _AsyncStreamIterator(response, self, name, args, kwargs)
            payloads = self.extractor.process_call(
                name, args, kwargs, response, client=self.client
            )
            if payloads:
                self.tracked_payloads.extend(payloads)
                for payload in payloads:
                    self.delivery.deliver({"usage_records": [payload]})
            return response

        return wrapper

    def get_tracked_payloads(self) -> list[dict[str, Any]]:
        """Return a copy of payloads generated so far."""
        return list(self.tracked_payloads)

    # ------------------------------------------------------------
    # delivery helpers
    # ------------------------------------------------------------
    def start_delivery(self) -> None:
        """Ensure the delivery worker is running."""
        self.delivery.start()

    async def stop_delivery(self) -> None:
        """Stop the delivery worker."""
        await self.delivery.stop()

    async def __aenter__(self) -> "AsyncCostManager":
        self.start_delivery()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop_delivery()
