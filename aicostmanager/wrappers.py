from __future__ import annotations

import inspect
from collections.abc import Iterable, AsyncIterable
from typing import Any

from .tracker import Tracker
from .usage_utils import get_usage_from_response, get_streaming_usage_from_response


class _Proxy:
    """Recursive proxy that intercepts method calls for tracking."""

    def __init__(self, obj: Any, wrapper: "BaseLLMWrapper") -> None:
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_wrapper", wrapper)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._obj, name)
        if callable(attr):
            if inspect.iscoroutinefunction(attr):
                async def async_call(*args, **kwargs):
                    model = self._wrapper._extract_model(attr, args, kwargs)
                    result = await attr(*args, **kwargs)
                    return await self._wrapper._handle_async_result(result, model)

                return async_call
            else:
                def sync_call(*args, **kwargs):
                    model = self._wrapper._extract_model(attr, args, kwargs)
                    result = attr(*args, **kwargs)
                    return self._wrapper._handle_result(result, model)

                return sync_call
        return _Proxy(attr, self._wrapper) if _should_wrap(attr) else attr

    def __call__(self, *args, **kwargs):
        model = self._wrapper._extract_model(self._obj, args, kwargs)
        result = self._obj(*args, **kwargs)
        return self._wrapper._handle_result(result, model)


def _should_wrap(obj: Any) -> bool:
    return not isinstance(
        obj,
        (
            str,
            bytes,
            bytearray,
            int,
            float,
            bool,
            type(None),
        ),
    )


class BaseLLMWrapper:
    """Base wrapper that tracks usage for LLM SDK clients."""

    api_id: str
    vendor_name: str = ""

    def __init__(
        self,
        client: Any,
        *,
        aicm_api_key: str | None = None,
        tracker: Tracker | None = None,
    ) -> None:
        self._client = client
        self._tracker = tracker or Tracker(aicm_api_key=aicm_api_key)
        self._proxy = _Proxy(client, self)

    # ------------------------------------------------------------------
    def _extract_model(self, method: Any, args: tuple, kwargs: dict) -> str | None:
        for key in ("model", "model_id", "modelId"):
            if key in kwargs:
                return kwargs[key]
        try:
            sig = inspect.signature(method)
            params = list(sig.parameters)
            for idx, name in enumerate(params):
                if name in ("model", "model_id", "modelId") and idx < len(args):
                    return args[idx]
        except (ValueError, TypeError):
            pass
        return None

    def _get_vendor(self) -> str:
        return self.vendor_name

    def _build_service_key(self, model: str | None) -> str:
        vendor = self._get_vendor()
        model_id = model or "unknown-model"
        return f"{vendor}::{model_id}"

    def _track_usage(self, response: Any, model: str | None) -> Any:
        usage = get_usage_from_response(response, self.api_id)
        if usage:
            response_id = getattr(response, "id", None)
            self._tracker.track(
                self.api_id,
                self._build_service_key(model),
                usage,
                response_id=response_id,
            )
        return response

    def _wrap_stream(self, stream: Iterable, model: str | None) -> Iterable:
        service_key = self._build_service_key(model)
        usage_sent = False
        for chunk in stream:
            if not usage_sent:
                usage = get_streaming_usage_from_response(chunk, self.api_id)
                if usage:
                    self._tracker.track(self.api_id, service_key, usage)
                    usage_sent = True
            yield chunk

    async def _wrap_stream_async(self, stream: AsyncIterable, model: str | None):
        service_key = self._build_service_key(model)
        usage_sent = False
        async for chunk in stream:
            if not usage_sent:
                usage = get_streaming_usage_from_response(chunk, self.api_id)
                if usage:
                    await self._tracker.track_async(
                        self.api_id, service_key, usage
                    )
                    usage_sent = True
            yield chunk

    def _handle_result(self, result: Any, model: str | None):
        if isinstance(result, AsyncIterable):
            return self._wrap_stream_async(result, model)
        if isinstance(result, Iterable) and not isinstance(
            result, (str, bytes, bytearray, dict)
        ):
            return self._wrap_stream(result, model)
        return self._track_usage(result, model)

    async def _handle_async_result(self, result: Any, model: str | None):
        if isinstance(result, AsyncIterable):
            return self._wrap_stream_async(result, model)
        if isinstance(result, Iterable) and not isinstance(
            result, (str, bytes, bytearray, dict)
        ):
            return self._wrap_stream(result, model)
        return self._track_usage(result, model)

    # ------------------------------------------------------------------
    def __getattr__(self, name: str) -> Any:  # pragma: no cover - delegated
        return getattr(self._proxy, name)

    def close(self) -> None:  # pragma: no cover - simple passthrough
        self._tracker.close()

    def __del__(self):  # pragma: no cover - cleanup
        try:
            self.close()
        except Exception:
            pass


class OpenAIChatWrapper(BaseLLMWrapper):
    api_id = "openai_chat"
    vendor_name = "openai"

    def _get_vendor(self) -> str:  # pragma: no cover - simple logic
        base_url = getattr(self._client, "base_url", "")
        if not base_url and hasattr(self._client, "client"):
            base_url = getattr(self._client.client, "base_url", "")
        if not base_url and hasattr(self._client, "_client"):
            base_url = getattr(self._client._client, "base_url", "")
        url = str(base_url).lower()
        if "fireworks.ai" in url:
            return "fireworks-ai"
        if "x.ai" in url:
            return "xai"
        return "openai"


class OpenAIResponsesWrapper(BaseLLMWrapper):
    api_id = "openai_responses"
    vendor_name = "openai"


class AnthropicWrapper(BaseLLMWrapper):
    api_id = "anthropic"
    vendor_name = "anthropic"


class GeminiWrapper(BaseLLMWrapper):
    api_id = "gemini"
    vendor_name = "google"


class BedrockWrapper(BaseLLMWrapper):
    api_id = "bedrock"
    vendor_name = "amazon-bedrock"


__all__ = [
    "OpenAIChatWrapper",
    "OpenAIResponsesWrapper",
    "AnthropicWrapper",
    "GeminiWrapper",
    "BedrockWrapper",
]
