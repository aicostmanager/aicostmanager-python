"""Utilities for extracting usage information from LLM API responses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _to_serializable_dict(data: Any, _seen: set[int] | None = None) -> dict[str, Any]:
    """Convert usage objects to plain dictionaries."""
    if data is None:
        return {}

    # Cycle detection
    if _seen is None:
        _seen = set()

    # Use object id to detect cycles
    obj_id = id(data)
    if obj_id in _seen:
        return str(data)  # Return string representation to break cycle
    _seen.add(obj_id)

    try:
        if isinstance(data, Mapping):
            # Filter out keys that start with underscore (private methods/attributes)
            result = {}
            for k, v in data.items():
                if isinstance(k, str) and not k.startswith("_"):
                    try:
                        result[k] = _to_serializable_dict(v, _seen)
                    except (TypeError, ValueError):
                        # Skip values that can't be serialized
                        continue
            return result
        if isinstance(data, (list, tuple)):
            return [
                _to_serializable_dict(v, _seen)
                for v in data
                if not _is_unsafe_object(v)
            ]

        # Pydantic models and dataclasses may provide model_dump or __dict__
        if hasattr(data, "model_dump"):
            return _to_serializable_dict(data.model_dump(), _seen)
        if hasattr(data, "to_dict"):
            return _to_serializable_dict(data.to_dict(), _seen)
        if hasattr(data, "__dict__"):
            return _to_serializable_dict(vars(data), _seen)

        # Check if this is a safe primitive type
        if _is_safe_primitive(data):
            return data

        # For other objects, try to get a string representation
        return str(data)
    finally:
        # Remove from seen set when done
        _seen.discard(obj_id)


def _is_unsafe_object(obj: Any) -> bool:
    """Check if an object contains unsafe content for JSON serialization."""
    if callable(obj):
        return True
    if hasattr(obj, "__dict__"):
        # Check if any attributes are callable
        for attr_name in dir(obj):
            if not attr_name.startswith("_"):
                attr = getattr(obj, attr_name, None)
                if callable(attr):
                    return True
    return False


def _is_safe_primitive(obj: Any) -> bool:
    """Check if an object is a safe primitive type for JSON serialization."""
    return isinstance(obj, (str, int, float, bool)) or obj is None


def _normalize_gemini_usage(usage: Any) -> dict[str, Any]:
    """Normalize Gemini usage data to match server schema expectations."""
    if not isinstance(usage, dict):
        return {}

    # Map snake_case keys to the expected camelCase keys
    key_map = {
        "prompt_token_count": "promptTokenCount",
        "candidates_token_count": "candidatesTokenCount",
        "total_token_count": "totalTokenCount",
    }

    normalized: dict[str, Any] = {}
    for k, v in usage.items():
        if k in ("promptTokenCount", "candidatesTokenCount", "totalTokenCount"):
            normalized[k] = v
        elif k in key_map:
            normalized[key_map[k]] = v

    # Only include keys allowed by server schema to avoid "additional properties" errors
    allowed = {"promptTokenCount", "candidatesTokenCount", "totalTokenCount"}
    return {k: v for k, v in normalized.items() if k in allowed}


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


def extract_usage(response: Any) -> dict[str, Any]:
    """Extract usage information from response if present.

    This is a compatibility function that delegates to get_usage_from_response
    with a generic approach for backward compatibility.
    """
    if response is None:
        return {}

    # Try to use the more specific API-aware function first
    # For known API patterns, we can try to infer the API type
    if hasattr(response, "usage") and hasattr(response.usage, "prompt_tokens"):
        # Looks like OpenAI format
        return get_usage_from_response(response, "openai_chat")
    elif hasattr(response, "usage_metadata"):
        # Looks like Gemini format
        usage = get_usage_from_response(response, "gemini")
        # Normalize Gemini usage to match server schema expectations
        return usage
        # return _normalize_gemini_usage(usage)
    elif hasattr(response, "input_tokens") or hasattr(response, "inputTokens"):
        # Looks like Anthropic/Bedrock format
        return get_usage_from_response(response, "anthropic")

    # Fallback to generic extraction
    for attr in ("usage", "usage_metadata", "response_metadata"):
        data = getattr(response, attr, None)
        if data is not None:
            return _to_serializable_dict(data)

    # Handle dictionary responses
    if isinstance(response, dict):
        for key in ("usage", "usageMetadata"):
            data = response.get(key)
            if data:
                return _to_serializable_dict(data)
        metadata = response.get("metadata")
        if isinstance(metadata, dict):
            for key in ("usage", "usageMetadata"):
                data = metadata.get(key)
                if data:
                    return _to_serializable_dict(data)

    return {}


def extract_stream_usage(stream: Any) -> tuple[dict[str, Any], Any]:
    """Consume a streaming iterator and return (usage, final_item).

    This function consumes the entire stream to get the final item,
    then extracts usage information from it.
    """
    final: Any = None

    # Consume the stream to get the final item
    if hasattr(stream, "__iter__"):
        for event in stream:
            final = event

    # Some SDKs provide helper methods to retrieve the final message/response
    if final is None:
        for attr in ("get_final_response", "get_final_message", "response"):
            obj = getattr(stream, attr, None)
            if callable(obj):
                try:
                    final = obj()
                    break
                except Exception:  # pragma: no cover - safety
                    pass
            elif obj is not None:
                final = obj
                break

    usage = extract_usage(final)
    return usage, final


__all__ = [
    "get_usage_from_response",
    "get_streaming_usage_from_response",
    "extract_usage",
    "extract_stream_usage",
]
