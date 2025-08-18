"""Asynchronous variant of :class:`CostManager`."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .client import (
    AsyncCostManagerClient,
    CostManagerClient,
    UsageLimitExceeded,
)
from .config_manager import Config, CostManagerConfig, TriggeredLimit
from .cost_manager import _AsyncStreamIterator
from .universal_extractor import UniversalExtractor


class AsyncResilientDelivery:
    """Asyncio based delivery queue with retry logic."""

    def __init__(
        self,
        session: Any,
        api_root: str,
        *,
        endpoint: str = "/track-usage",
        max_retries: int = 5,
        queue_size: int = 10000,
        timeout: float = 10.0,
        ini_path: Optional[str] = None,
        batch_interval: float | None = None,
        max_batch_size: int = 1000,
    ) -> None:
        self.session = session
        self.api_root = api_root.rstrip("/")
        self.endpoint = endpoint
        self.max_retries = max_retries
        self.timeout = timeout
        self.ini_path = ini_path
        self.max_batch_size = max_batch_size
        self.batch_interval = batch_interval if batch_interval is not None else 0.5
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
            loop = asyncio.get_running_loop()
            deadline = loop.time() + self.batch_interval
            while len(batch) < self.max_batch_size:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    nxt = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                    batch.append(nxt)
                except asyncio.TimeoutError:
                    break
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
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        delivery: AsyncResilientDelivery | None = None,
        delivery_queue_size: int = 10000,
        delivery_max_retries: int = 5,
        delivery_timeout: float = 10.0,
        delivery_batch_interval: float | None = None,
        delivery_max_batch_size: int = 1000,
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
        self.api_id = client.__class__.__module__.lower()
        self.configs: List[Config] = self.config_manager.get_config(self.api_id)
        cfg_client.close()
        self.extractor = UniversalExtractor(self.configs)
        self.tracked_payloads: list[dict[str, Any]] = []
        self.triggered_limits: List[TriggeredLimit] = []
        self.client_customer_key = client_customer_key
        self.context = context

        if delivery is not None:
            self.delivery = delivery
        else:
            self.delivery = AsyncResilientDelivery(
                self.cm_client.session,
                self.cm_client.api_root,
                max_retries=delivery_max_retries,
                queue_size=delivery_queue_size,
                timeout=delivery_timeout,
                ini_path=aicm_ini_path,
                batch_interval=delivery_batch_interval,
                max_batch_size=delivery_max_batch_size,
            )
        self.delivery.start()

    def _refresh_limits(self) -> None:
        """Load latest triggered limits from the config manager."""
        try:
            self.triggered_limits = self.config_manager.get_triggered_limits(
                client_customer_key=self.client_customer_key
            )
            blocking_limits = [
                limit
                for limit in self.triggered_limits
                if limit.threshold_type == "limit"
            ]
            if blocking_limits:
                raise UsageLimitExceeded(blocking_limits)
        except UsageLimitExceeded:
            raise
        except Exception:
            self.triggered_limits = []

    def set_client_customer_key(self, client_customer_key: Optional[str]) -> None:
        self.client_customer_key = client_customer_key

    def set_context(self, context: Optional[Dict[str, Any]]) -> None:
        self.context = context

    def _augment_payload(self, payload: dict[str, Any]) -> None:
        if self.client_customer_key and payload.get("client_customer_key") is None:
            payload["client_customer_key"] = self.client_customer_key
        if self.context and payload.get("context") is None:
            payload["context"] = self.context

    # ------------------------------------------------------------
    # attribute proxying
    # ------------------------------------------------------------
    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.client, name)

        if not callable(attr):
            self._refresh_limits()
            return AsyncNestedAttributeWrapper(attr, self, name)

        async def wrapper(*args, **kwargs):
            self._refresh_limits()
            response = await attr(*args, **kwargs)
            if kwargs.get("stream") and hasattr(response, "__aiter__"):
                return _AsyncStreamIterator(response, self, name, args, kwargs)
            payloads = self.extractor.process_call(
                name, args, kwargs, response, client=self.client
            )
            if payloads:
                if self.api_id == "openai":
                    service_model = kwargs.get("model")
                    for payload in payloads:
                        if service_model and "service_id" not in payload:
                            payload["service_id"] = service_model
                self.tracked_payloads.extend(payloads)
                for payload in payloads:
                    self._augment_payload(payload)
                    self.delivery.deliver({"usage_records": [payload]})
            return response

        return wrapper

    def get_tracked_payloads(self) -> list[dict[str, Any]]:
        """Return a copy of payloads generated so far."""
        return list(self.tracked_payloads)

    # ------------------------------------------------------------
    # streaming detection helpers (mirrored from CostManager)
    # ------------------------------------------------------------
    def _is_streaming(self, result: Any) -> bool:
        """Determine if result is streaming using multiple detection methods."""
        return (
            self._is_streaming_type(result)
            or self._appears_to_be_stream(result)
            or self._has_streaming_interface(result)
            or self._is_bedrock_streaming(result)
        )

    def _is_streaming_type(self, result: Any) -> bool:
        """Check type-based indicators for streaming."""
        import inspect
        from typing import AsyncGenerator, AsyncIterator, Generator, Iterator

        if isinstance(result, (Iterator, AsyncIterator, Generator, AsyncGenerator)):
            return True

        if inspect.isgenerator(result) or inspect.isasyncgen(result):
            return True

        return False

    def _appears_to_be_stream(self, result: Any) -> bool:
        """Check duck-typing indicators for streaming."""
        class_name = type(result).__name__.lower()
        if any(
            indicator in class_name for indicator in ["stream", "iterator", "chunk"]
        ):
            return True

        if hasattr(result, "__iter__") and hasattr(result, "__next__"):
            return True

        if hasattr(result, "__aiter__") and hasattr(result, "__anext__"):
            return True

        return False

    def _has_streaming_interface(self, result: Any) -> bool:
        """Check for streaming-specific methods."""
        streaming_methods = [
            "read",
            "readline",
            "__stream__",
            "iter_lines",
            "iter_content",
        ]
        return any(hasattr(result, method) for method in streaming_methods)

    def _is_bedrock_streaming(self, result: Any) -> bool:
        """Check for Bedrock-specific streaming response structure."""
        if isinstance(result, dict) and "stream" in result:
            stream_obj = result["stream"]
            is_bedrock_stream = (
                hasattr(stream_obj, "__iter__")
                and not isinstance(stream_obj, (str, bytes, dict))
                and (
                    hasattr(stream_obj, "__next__")
                    or "EventStream" in str(type(stream_obj))
                )
            )
            return is_bedrock_stream
        return False

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


class AsyncNestedAttributeWrapper:
    """Async wrapper for nested attributes supporting limit enforcement."""

    def __init__(self, obj: Any, parent_manager: AsyncCostManager, path: str) -> None:
        self._wrapped_obj = obj
        self._parent_manager = parent_manager
        self._path = path

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._wrapped_obj, name)
        full_path = f"{self._path}.{name}"

        if callable(attr):

            async def wrapper(*args, **kwargs):
                self._parent_manager._refresh_limits()
                if (
                    kwargs.get("stream")
                    and self._parent_manager.api_id == "openai"
                    and full_path in ["chat.completions.create", "completions.create"]
                ):
                    if "stream_options" not in kwargs:
                        kwargs["stream_options"] = {"include_usage": True}

                response = await attr(*args, **kwargs)
                if self._parent_manager._is_streaming(response):
                    return _AsyncStreamIterator(
                        response, self._parent_manager, full_path, args, kwargs
                    )
                payloads = self._parent_manager.extractor.process_call(
                    full_path,
                    args,
                    kwargs,
                    response,
                    client=self._parent_manager.client,
                    is_streaming=False,
                )
                if payloads:
                    if self._parent_manager.api_id == "openai":
                        service_model = kwargs.get("model")
                        for payload in payloads:
                            if service_model and "service_id" not in payload:
                                payload["service_id"] = service_model
                    self._parent_manager.tracked_payloads.extend(payloads)
                    for payload in payloads:
                        self._parent_manager._augment_payload(payload)
                        self._parent_manager.delivery.deliver(
                            {"usage_records": [payload]}
                        )
                return response

            return wrapper
        else:
            self._parent_manager._refresh_limits()
            return AsyncNestedAttributeWrapper(attr, self._parent_manager, full_path)
