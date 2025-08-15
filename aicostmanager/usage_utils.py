"""Utilities for extracting usage information from LLM API responses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _to_serializable_dict(data: Any) -> dict[str, Any]:
    """Convert usage objects to plain dictionaries."""
    if data is None:
        return {}
    if isinstance(data, Mapping):
        return {k: _to_serializable_dict(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_to_serializable_dict(v) for v in data]
    # Pydantic models and dataclasses may provide model_dump or __dict__
    if hasattr(data, "model_dump"):
        return _to_serializable_dict(data.model_dump())
    if hasattr(data, "to_dict"):
        return _to_serializable_dict(data.to_dict())
    if hasattr(data, "__dict__"):
        return _to_serializable_dict(vars(data))
    return data


def get_usage_from_response(response: Any, api_id: str) -> dict[str, Any]:
    """Return JSON-serializable usage info from an API response."""
    usage: Any = None
    if api_id in {"openai_chat", "openai_responses"}:
        usage = getattr(response, "usage", None)
    elif api_id == "anthropic":
        usage = (
            response if not hasattr(response, "usage") else getattr(response, "usage")
        )
    elif api_id == "bedrock":
        if isinstance(response, Mapping):
            if "usage" in response:
                usage = response["usage"]
            elif all(
                k in response for k in ("inputTokens", "outputTokens", "totalTokens")
            ):
                usage = response
            elif "ResponseMetadata" in response and "usage" in response:
                usage = response.get("usage")
        else:
            usage = getattr(response, "usage", None)
    elif api_id == "gemini":
        usage = getattr(response, "usage_metadata", None)
    return _to_serializable_dict(usage)


def _get_field_value(meta: Any, camel_case: str, snake_case: str) -> Any:
    """Get field value trying both camelCase and snake_case variants."""
    if hasattr(meta, camel_case):
        value = getattr(meta, camel_case)
        if value is not None:
            return value
    if hasattr(meta, snake_case):
        value = getattr(meta, snake_case)
        if value is not None:
            return value
    if isinstance(meta, Mapping):
        value = meta.get(camel_case)
        if value is not None:
            return value
        value = meta.get(snake_case)
        if value is not None:
            return value
    return None


def get_streaming_usage_from_response(chunk: Any, api_id: str) -> dict[str, Any]:
    """Extract usage information from streaming response chunks."""
    usage: Any = None
    if api_id in {"openai_chat", "openai_responses"}:
        # Some SDKs put usage directly on the event
        usage = getattr(chunk, "usage", None)
        # Responses API events often nest usage on the inner .response
        if (
            not usage
            and hasattr(chunk, "response")
            and hasattr(chunk.response, "usage")
        ):
            usage = getattr(chunk.response, "usage")
        # Raw/dict fallbacks
        if not usage and isinstance(chunk, Mapping):
            usage = chunk.get("usage") or (chunk.get("response", {}) or {}).get("usage")

    elif api_id == "anthropic":
        if hasattr(chunk, "usage"):
            usage = getattr(chunk, "usage")
        elif hasattr(chunk, "message") and hasattr(chunk.message, "usage"):
            usage = getattr(chunk.message, "usage")

    elif api_id == "bedrock":
        if isinstance(chunk, Mapping):
            if "metadata" in chunk and "usage" in chunk["metadata"]:
                usage = chunk["metadata"]["usage"]
            elif "usage" in chunk:
                usage = chunk["usage"]

    elif api_id == "gemini":
        # 1) direct on the event
        meta = getattr(chunk, "usage_metadata", None)
        # 2) sometimes nested under .model_response.usage_metadata
        if meta is None and hasattr(chunk, "model_response"):
            meta = getattr(chunk.model_response, "usage_metadata", None)
        # 3) dict-like fallback
        if meta is None and isinstance(chunk, Mapping):
            model_resp = chunk.get("model_response")
            meta = chunk.get("usage_metadata") or (
                (model_resp or {}).get("usage_metadata")
                if isinstance(model_resp, Mapping)
                else None
            )

        if meta is not None:
            # Build a minimal serializable dict supporting both camelCase and snake_case
            # Field mappings: (camelCase, snake_case, output_key)
            field_mappings = [
                ("promptTokenCount", "prompt_token_count", "promptTokenCount"),
                (
                    "candidatesTokenCount",
                    "candidates_token_count",
                    "candidatesTokenCount",
                ),
                ("totalTokenCount", "total_token_count", "totalTokenCount"),
                ("thoughtsTokenCount", "thoughts_token_count", "thoughtsTokenCount"),
                (
                    "toolUsePromptTokenCount",
                    "tool_use_prompt_token_count",
                    "toolUsePromptTokenCount",
                ),
                (
                    "cachedContentTokenCount",
                    "cached_content_token_count",
                    "cachedContentTokenCount",
                ),
            ]

            usage = {}
            for camel_case, snake_case, output_key in field_mappings:
                value = _get_field_value(meta, camel_case, snake_case)
                if value is not None:
                    usage[output_key] = value
        else:
            usage = None

    return _to_serializable_dict(usage)
