"""Client wrappers for automatic usage tracking."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterator, Optional

from ..client import AsyncCostManagerClient, CostManagerClient
from ..delivery import ResilientDelivery, _ini_get_or_set, get_global_delivery
from .base import BaseCostManager


class NestedAttributeWrapper:
    """Proxy object to handle nested attributes like client.chat.completions."""

    def __init__(self, attr: Any, manager: "ClientCostManager", path: str) -> None:
        self._attr = attr
        self._manager = manager
        self._path = path

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._attr, name)
        full_path = f"{self._path}.{name}" if self._path else name
        if callable(attr):

            def wrapper(*args, **kwargs):
                return getattr(self._manager, full_path)(*args, **kwargs)

            return wrapper
        return NestedAttributeWrapper(attr, self._manager, full_path)


class _StreamIterator:
    """Iterator proxy that records streaming results when iteration ends."""

    def __init__(
        self,
        iterator: Iterator[Any],
        manager: "ClientCostManager",
        name: str,
        args: tuple,
        kwargs: dict,
    ) -> None:
        self.iterator = iterator
        self.manager = manager
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self._last_item: Any = None
        self._response_id: Any = None
        self._usage_snapshot: Any = None

    def __iter__(self):
        return self

    def __next__(self):
        try:
            item = next(self.iterator)
            self._last_item = item
            try:
                if hasattr(item, "id") and getattr(item, "id"):
                    self._response_id = getattr(item, "id")
                if hasattr(item, "response") and hasattr(item.response, "id"):
                    self._response_id = getattr(item.response, "id")
                if hasattr(item, "usage") and getattr(item, "usage") is not None:
                    self._usage_snapshot = getattr(item, "usage")
                if hasattr(item, "response") and hasattr(item.response, "usage"):
                    self._usage_snapshot = getattr(item.response, "usage")
            except Exception:
                pass
            return item
        except StopIteration:
            # When the underlying stream is exhausted, process and deliver usage
            try:
                self.close()
            finally:
                pass
            raise

    def close(self):  # type: ignore[override]
        if hasattr(self.iterator, "close"):
            self.iterator.close()
        # Build a synthetic final response that includes id/usage captured from chunks
        final_response = {
            "id": self._response_id,
            "usage": self._usage_snapshot,
            "response": {"id": self._response_id, "usage": self._usage_snapshot},
            "last_chunk": self._last_item,
        }
        payloads = self.manager.extractor.process_call(
            self.name,
            self.args,
            self.kwargs,
            final_response,
            client=self.manager.client,
            is_streaming=True,
        )
        if payloads:
            if self.manager.api_id == "openai":
                service_model = self.kwargs.get("model")
                for payload in payloads:
                    # Ensure response_id is present for server-side correlation
                    if self._response_id and not payload.get("response_id"):
                        payload["response_id"] = self._response_id
                    if service_model and not payload.get("service_id"):
                        payload["service_id"] = service_model
            # Ensure usage is a dict, never None (some providers omit it in streams)
            for payload in payloads:
                if payload.get("usage") is None:
                    payload["usage"] = {}
            self.manager.tracked_payloads.extend(payloads)
            for payload in payloads:
                self.manager._augment_payload(payload)
                try:
                    print(f"[AICM DEBUG] streaming payload: {payload}")
                except Exception:
                    pass
                self.manager.delivery.deliver({"usage_records": [payload]})


class AsyncNestedAttributeWrapper:
    """Async variant of :class:`NestedAttributeWrapper`."""

    def __init__(self, attr: Any, manager: "AsyncClientCostManager", path: str) -> None:
        self._attr = attr
        self._manager = manager
        self._path = path

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._attr, name)
        full_path = f"{self._path}.{name}" if self._path else name
        if callable(attr):

            async def wrapper(*args, **kwargs):
                return await getattr(self._manager, full_path)(*args, **kwargs)

            return wrapper
        return AsyncNestedAttributeWrapper(attr, self._manager, full_path)


class _AsyncStreamIterator:
    """Async iterator proxy that records streaming results when iteration ends."""

    def __init__(
        self,
        iterator: Any,
        manager: "AsyncClientCostManager",
        name: str,
        args: tuple,
        kwargs: dict,
    ) -> None:
        self.iterator = iterator
        self.manager = manager
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self._last_item: Any = None
        self._response_id: Any = None
        self._usage_snapshot: Any = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            item = await self.iterator.__anext__()
            self._last_item = item
            try:
                if hasattr(item, "id") and getattr(item, "id"):
                    self._response_id = getattr(item, "id")
                if hasattr(item, "response") and hasattr(item.response, "id"):
                    self._response_id = getattr(item.response, "id")
                if hasattr(item, "usage") and getattr(item, "usage") is not None:
                    self._usage_snapshot = getattr(item, "usage")
                if hasattr(item, "response") and hasattr(item.response, "usage"):
                    self._usage_snapshot = getattr(item.response, "usage")
            except Exception:
                pass
            return item
        except StopAsyncIteration:
            # When the underlying async stream is exhausted, process and deliver usage
            try:
                await self.aclose()
            finally:
                pass
            raise

    async def aclose(self):  # type: ignore[override]
        if hasattr(self.iterator, "aclose"):
            await self.iterator.aclose()
        final_response = {
            "id": self._response_id,
            "usage": self._usage_snapshot,
            "response": {"id": self._response_id, "usage": self._usage_snapshot},
            "last_chunk": self._last_item,
        }
        payloads = self.manager.extractor.process_call(
            self.name,
            self.args,
            self.kwargs,
            final_response,
            client=self.manager.client,
            is_streaming=True,
        )
        if payloads:
            if self.manager.api_id == "openai":
                service_model = self.kwargs.get("model")
                for payload in payloads:
                    if self._response_id and not payload.get("response_id"):
                        payload["response_id"] = self._response_id
                    if service_model and not payload.get("service_id"):
                        payload["service_id"] = service_model
            for payload in payloads:
                if payload.get("usage") is None:
                    payload["usage"] = {}
            self.manager.tracked_payloads.extend(payloads)
            for payload in payloads:
                self.manager._augment_payload(payload)
                try:
                    print(f"[AICM DEBUG] streaming payload (async): {payload}")
                except Exception:
                    pass
                self.manager.delivery.deliver({"usage_records": [payload]})


class ClientCostManager(BaseCostManager):
    """Wrap a client to automatically track usage."""

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
        delivery: ResilientDelivery | None = None,
        delivery_queue_size: int = 1000,
        delivery_max_retries: int = 5,
        delivery_timeout: float = 10.0,
        delivery_batch_interval: float | None = None,
        delivery_max_batch_size: int = 100,
        delivery_mode: str | None = None,
        delivery_on_full: str | None = None,
    ) -> None:
        cm_client = CostManagerClient(
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
        )
        if delivery is None:
            delivery = get_global_delivery(
                cm_client,
                max_retries=delivery_max_retries,
                queue_size=delivery_queue_size,
                timeout=delivery_timeout,
                batch_interval=delivery_batch_interval,
                max_batch_size=delivery_max_batch_size,
                delivery_mode=delivery_mode,
                on_full=delivery_on_full,
            )
        super().__init__(
            client,
            config_client=cm_client,
            cm_client=cm_client,
            client_customer_key=client_customer_key,
            context=context,
            delivery=delivery,
        )

    # attribute proxying -------------------------------------------------
    def __getattr__(self, name: str) -> Any:
        # Resolve top-level attribute for normal attribute access (e.g., track_client.chat)
        if "." not in name:
            attr = getattr(self.client, name)
            if callable(attr):

                def wrapper(*args, **kwargs):
                    self._refresh_limits()
                    call_name = name
                    if (
                        kwargs.get("stream")
                        and self.api_id == "openai"
                        and call_name
                        in ["completions.create", "chat.completions.create"]
                    ):
                        if "stream_options" not in kwargs:
                            kwargs["stream_options"] = {"include_usage": True}
                    response = attr(*args, **kwargs)
                    if self._is_streaming(response):
                        return _StreamIterator(response, self, call_name, args, kwargs)
                    payloads = self.extractor.process_call(
                        call_name,
                        args,
                        kwargs,
                        response,
                        client=self.client,
                        is_streaming=False,
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
            else:
                self._refresh_limits()
                return NestedAttributeWrapper(attr, self, name)

        # Support dotted attribute paths coming from NestedAttributeWrapper
        def _resolve_attr(path: str) -> Any:
            target = self.client
            for part in path.split("."):
                target = getattr(target, part)
            return target

        attr = _resolve_attr(name)
        if not callable(attr):
            # Should not generally happen because dotted resolution is only used for callables
            self._refresh_limits()
            return NestedAttributeWrapper(attr, self, name)

        def wrapper(*args, **kwargs):
            self._refresh_limits()
            call_name = name
            if (
                kwargs.get("stream")
                and self.api_id == "openai"
                and call_name in ["completions.create", "chat.completions.create"]
            ):
                if "stream_options" not in kwargs:
                    kwargs["stream_options"] = {"include_usage": True}
            response = attr(*args, **kwargs)
            if self._is_streaming(response):
                return _StreamIterator(response, self, call_name, args, kwargs)
            payloads = self.extractor.process_call(
                call_name,
                args,
                kwargs,
                response,
                client=self.client,
                is_streaming=False,
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

    # delivery helpers ---------------------------------------------------
    def start_delivery(self) -> None:
        self.delivery.start()

    def stop_delivery(self) -> None:
        self.delivery.stop()

    def __enter__(self) -> "ClientCostManager":
        self.start_delivery()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop_delivery()


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
        ini_path: Optional[str] = None,
        batch_interval: float | None = None,
        max_batch_size: int = 100,
    ) -> None:
        self.session = session
        self.api_root = api_root.rstrip("/")
        self.endpoint = endpoint
        self.max_retries = max_retries
        self.timeout = timeout
        self.ini_path = ini_path
        self.max_batch_size = max_batch_size
        if ini_path:
            default_interval = batch_interval if batch_interval is not None else 0.05
            override = batch_interval is not None
            self.batch_interval = _ini_get_or_set(
                ini_path, "delivery", "timeout", default_interval, override=override
            )
        else:
            self.batch_interval = batch_interval if batch_interval is not None else 0.05
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_size)
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._total_sent = 0
        self._total_failed = 0
        self._last_error: str | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        await self._queue.put({})
        await self._task
        self._task = None

    def deliver(self, payload: dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            logging.warning("Delivery queue full - dropping payload")

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
        except Exception as exc:  # pragma: no cover
            logging.error("Failed to deliver payload after retries: %s", exc)
            self._total_failed += 1
            self._last_error = str(exc)

    def get_health_info(self) -> dict[str, Any]:
        return {
            "worker_alive": self._task is not None and not self._task.done(),
            "queue_size": self._queue.qsize(),
            "queue_utilization": self._queue.qsize() / self._queue.maxsize,
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "last_error": self._last_error,
        }


class AsyncClientCostManager(BaseCostManager):
    """Async wrapper for API clients."""

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
        delivery_queue_size: int = 1000,
        delivery_max_retries: int = 5,
        delivery_timeout: float = 10.0,
        delivery_batch_interval: float | None = None,
        delivery_max_batch_size: int = 100,
    ) -> None:
        cfg_client = CostManagerClient(
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
        )
        cm_client = AsyncCostManagerClient(
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
        )
        if delivery is None:
            delivery = AsyncResilientDelivery(
                cm_client.session,
                cm_client.api_root,
                max_retries=delivery_max_retries,
                queue_size=delivery_queue_size,
                timeout=delivery_timeout,
                ini_path=aicm_ini_path,
                batch_interval=delivery_batch_interval,
                max_batch_size=delivery_max_batch_size,
            )
        super().__init__(
            client,
            config_client=cfg_client,
            cm_client=cm_client,
            client_customer_key=client_customer_key,
            context=context,
            delivery=delivery,
        )
        cfg_client.close()
        self.delivery.start()

    # attribute proxying -------------------------------------------------
    def __getattr__(self, name: str) -> Any:
        # Resolve top-level attribute for normal attribute access (e.g., track_client.chat)
        if "." not in name:
            attr = getattr(self.client, name)
            if not callable(attr):
                self._refresh_limits()
                return AsyncNestedAttributeWrapper(attr, self, name)

            async def wrapper(*args, **kwargs):
                self._refresh_limits()
                call_name = name
                # Inject include_usage for OpenAI streaming chat completions
                if (
                    kwargs.get("stream")
                    and self.api_id == "openai"
                    and call_name in ["completions.create", "chat.completions.create"]
                ):
                    if "stream_options" not in kwargs:
                        kwargs["stream_options"] = {"include_usage": True}
                response = await attr(*args, **kwargs)
                if kwargs.get("stream") and hasattr(response, "__aiter__"):
                    return _AsyncStreamIterator(response, self, call_name, args, kwargs)
                payloads = self.extractor.process_call(
                    call_name, args, kwargs, response, client=self.client
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

        # Support dotted attribute paths coming from AsyncNestedAttributeWrapper
        def _resolve_attr(path: str) -> Any:
            target = self.client
            for part in path.split("."):
                target = getattr(target, part)
            return target

        attr = _resolve_attr(name)
        if not callable(attr):
            # Should not generally happen because dotted resolution is only used for callables
            self._refresh_limits()
            return AsyncNestedAttributeWrapper(attr, self, name)

        async def wrapper(*args, **kwargs):
            self._refresh_limits()
            call_name = name
            if (
                kwargs.get("stream")
                and self.api_id == "openai"
                and call_name in ["completions.create", "chat.completions.create"]
            ):
                if "stream_options" not in kwargs:
                    kwargs["stream_options"] = {"include_usage": True}
            response = await attr(*args, **kwargs)
            if kwargs.get("stream") and hasattr(response, "__aiter__"):
                return _AsyncStreamIterator(response, self, call_name, args, kwargs)
            payloads = self.extractor.process_call(
                call_name, args, kwargs, response, client=self.client
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

    # delivery helpers ---------------------------------------------------
    def start_delivery(self) -> None:
        self.delivery.start()

    async def stop_delivery(self) -> None:
        await self.delivery.stop()

    async def __aenter__(self) -> "AsyncClientCostManager":
        self.start_delivery()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop_delivery()


__all__ = [
    "ClientCostManager",
    "AsyncClientCostManager",
    "AsyncResilientDelivery",
    "NestedAttributeWrapper",
    "AsyncNestedAttributeWrapper",
]
