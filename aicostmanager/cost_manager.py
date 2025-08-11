"""Light weight wrapper that coordinates a client with :class:`UniversalExtractor`."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Iterator, List, Optional
import weakref

from .client import CostManagerClient, UsageLimitExceeded
from .config_manager import Config, CostManagerConfig, TriggeredLimit
from .delivery import ResilientDelivery, get_global_delivery
from .universal_extractor import UniversalExtractor


class CostManager:
    """Wrap an API/LLM client to facilitate usage tracking.

    The class is intentionally simple.  On instantiation the provided
    client is stored and configuration for that client's ``api_id`` is
    loaded via :class:`CostManagerConfig`.  A single
    :class:`UniversalExtractor` instance is created using that list of
    :class:`Config` objects.  Subsequent method calls are proxied through
    to the wrapped client while allowing the extractor to build payloads
    describing the interaction.
    """

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
        self.client = client
        self.cm_client = CostManagerClient(
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
        )
        self.config_manager = CostManagerConfig(self.cm_client)
        self.api_id = client.__class__.__module__.lower()
        self.configs: List[Config] = self.config_manager.get_config(self.api_id)
        self.extractor = UniversalExtractor(self.configs)
        self.tracked_payloads: list[dict[str, Any]] = []
        self.triggered_limits: List[TriggeredLimit] = []
        self.client_customer_key = client_customer_key
        self.context = context

        if delivery is not None:
            self.delivery = delivery
        else:
            self.delivery = get_global_delivery(
                self.cm_client,
                max_retries=delivery_max_retries,
                queue_size=delivery_queue_size,
                timeout=delivery_timeout,
                batch_interval=delivery_batch_interval,
                max_batch_size=delivery_max_batch_size,
                delivery_mode=delivery_mode,
                on_full=delivery_on_full,
            )

    def _refresh_limits(self) -> None:
        """Load latest triggered limits from the config manager."""
        try:
            self.triggered_limits = self.config_manager.get_triggered_limits(
                client_customer_key=self.client_customer_key
            )
            # Check for LIMIT threshold types that should block API calls
            blocking_limits = [
                limit
                for limit in self.triggered_limits
                if limit.threshold_type == "limit"
            ]
            if blocking_limits:
                raise UsageLimitExceeded(blocking_limits)
        except UsageLimitExceeded:
            # Re-raise usage limit exceptions
            raise
        except Exception:
            # Only catch other types of exceptions
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

        if callable(attr):

            def wrapper(*args, **kwargs):
                self._refresh_limits()
                # Add stream_options for OpenAI clients to enable usage data in streaming
                # Only for endpoints that support stream_options (chat.completions and completions)
                if (
                    kwargs.get("stream")
                    and self.api_id == "openai"
                    and name in ["completions.create", "chat.completions.create"]
                ):
                    if "stream_options" not in kwargs:
                        kwargs["stream_options"] = {"include_usage": True}

                response = attr(*args, **kwargs)
                if self._is_streaming(response):
                    return _StreamIterator(response, self, name, args, kwargs)
                payloads = self.extractor.process_call(
                    name, args, kwargs, response, client=self.client, is_streaming=False
                )
                if payloads:
                    # Ensure service_id is present for OpenAI calls to allow service-scoped limits
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
            # For non-callable attributes, wrap them with a nested tracker
            # to handle cases like client.chat.completions.create()
            self._refresh_limits()
            return NestedAttributeWrapper(attr, self, name)

    def get_tracked_payloads(self) -> list[dict[str, Any]]:
        """Return a copy of payloads generated so far."""

        return list(self.tracked_payloads)

    # ------------------------------------------------------------
    # streaming detection helpers
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
        # Check class name
        class_name = type(result).__name__.lower()
        if any(
            indicator in class_name for indicator in ["stream", "iterator", "chunk"]
        ):
            return True

        # Check for iterator protocol
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
        # Bedrock streaming responses are dicts with a "stream" key containing the actual iterator
        if isinstance(result, dict) and "stream" in result:
            stream_obj = result["stream"]
            # Check if the nested stream object has iterator characteristics
            # EventStream objects have __iter__ but not __next__ (they're iterables, not iterators)
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
        """Ensure the global delivery worker is running."""

        self.delivery.start()

    def stop_delivery(self) -> None:
        """Stop the global delivery worker."""

        self.delivery.stop()

    def __enter__(self) -> "CostManager":
        self.start_delivery()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop_delivery()


class _StreamIterator:
    """Proxy iterator that tracks streaming responses after completion."""

    def __init__(
        self,
        iterator: Iterator,
        manager: "CostManager",
        method: str,
        args: tuple,
        kwargs: dict,
    ) -> None:
        self._iterator = iterator
        self._manager = manager
        self._method = method
        self._args = args
        self._kwargs = kwargs
        self._last = None
        self._finalized = False
        weakref.finalize(self, self._finalise_if_needed)

    def __iter__(self) -> Iterator:
        for item in self._iterator:
            self._last = item
            yield item
        # Only finalize if not already done (e.g., by nested iterator)
        if not self._finalized:
            self._finalise()
            self._finalized = True

    def __getitem__(self, key):
        """Proxy attribute access for nested streaming responses (e.g., Bedrock's stream["stream"])."""
        if hasattr(self._iterator, "__getitem__"):
            nested_item = self._iterator[key]
            # If accessing a nested iterator (like Bedrock's "stream" key), wrap it
            if hasattr(nested_item, "__iter__") and not isinstance(
                nested_item, (str, bytes)
            ):
                return _NestedStreamIterator(nested_item, self)
            return nested_item
        raise TypeError(
            f"'{type(self._iterator).__name__}' object is not subscriptable"
        )

    def __getattr__(self, name):
        """Proxy attribute access to the underlying iterator."""
        return getattr(self._iterator, name)

    def _finalise_if_needed(self) -> None:
        if not self._finalized:
            self._finalise()
            self._finalized = True

    def _finalise(self) -> None:
        # For Bedrock streaming, merge the original response metadata with the final chunk
        final_response = self._last
        if (
            hasattr(self._iterator, "get")
            and "ResponseMetadata" in self._iterator
            and isinstance(final_response, dict)
        ):
            # Merge ResponseMetadata from original response
            final_response = {
                **final_response,
                "ResponseMetadata": self._iterator["ResponseMetadata"],
            }

        payloads = self._manager.extractor.process_call(
            self._method,
            self._args,
            self._kwargs,
            final_response,
            client=self._manager.client,
            is_streaming=True,
        )
        if payloads:
            self._manager.tracked_payloads.extend(payloads)
            for payload in payloads:
                self._manager._augment_payload(payload)
                self._manager.delivery.deliver({"usage_records": [payload]})


class _NestedStreamIterator:
    """Handles nested streaming iterators (e.g., Bedrock's stream["stream"])."""

    def __init__(self, nested_iterator: Iterator, parent: "_StreamIterator") -> None:
        self._nested_iterator = nested_iterator
        self._parent = parent

    def __iter__(self) -> Iterator:
        for item in self._nested_iterator:
            self._parent._last = item  # Track the last item in the parent
            yield item
        # Finalize when nested iteration completes
        if not self._parent._finalized:
            self._parent._finalise()
            self._parent._finalized = True


class _AsyncStreamIterator:
    """Async variant of :class:`_StreamIterator`."""

    def __init__(
        self,
        iterator: Iterable,
        manager: "CostManager",
        method: str,
        args: tuple,
        kwargs: dict,
    ) -> None:
        self._iterator = iterator
        self._manager = manager
        self._method = method
        self._args = args
        self._kwargs = kwargs
        self._last = None
        self._finalized = False
        weakref.finalize(self, self._finalise_if_needed)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            item = await self._iterator.__anext__()
        except StopAsyncIteration:
            if not self._finalized:
                self._finalise()
                self._finalized = True
            raise
        else:
            self._last = item
            return item

    def _finalise(self) -> None:
        payloads = self._manager.extractor.process_call(
            self._method,
            self._args,
            self._kwargs,
            self._last,
            client=self._manager.client,
            is_streaming=True,
        )
        if payloads:
            self._manager.tracked_payloads.extend(payloads)
            for payload in payloads:
                self._manager._augment_payload(payload)
                self._manager.delivery.deliver({"usage_records": [payload]})

    def _finalise_if_needed(self) -> None:
        if not self._finalized:
            self._finalise()
            self._finalized = True


class NestedAttributeWrapper:
    """Wrapper for non-callable attributes to enable tracking of nested method calls."""

    def __init__(self, obj: Any, parent_manager: CostManager, path: str):
        self._wrapped_obj = obj
        self._parent_manager = parent_manager
        self._path = path

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._wrapped_obj, name)
        full_path = f"{self._path}.{name}"

        if callable(attr):

            def wrapper(*args, **kwargs):
                self._parent_manager._refresh_limits()
                # Add stream_options for OpenAI clients to enable usage data in streaming
                # Only for endpoints that support stream_options (chat.completions and completions)
                if (
                    kwargs.get("stream")
                    and self._parent_manager.api_id == "openai"
                    and full_path in ["chat.completions.create", "completions.create"]
                ):
                    if "stream_options" not in kwargs:
                        kwargs["stream_options"] = {"include_usage": True}

                response = attr(*args, **kwargs)
                if self._parent_manager._is_streaming(response):
                    return _StreamIterator(
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
            # Continue wrapping for deeper nesting
            self._parent_manager._refresh_limits()
            return NestedAttributeWrapper(attr, self._parent_manager, full_path)
