"""Utilities for extracting usage information from LLM API responses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _to_serializable_dict(data: Any, _seen: set[int] | None = None) -> dict[str, Any]:
    """Convert usage objects to plain dictionaries."""
    if data is None:
        return {}

    # Check for Mock/MagicMock objects early to avoid infinite recursion
    # MagicMock objects dynamically create attributes when accessed, which can
    # cause infinite loops when trying to serialize them
    if hasattr(data, "_mock_name") or type(data).__name__ in (
        "Mock",
        "MagicMock",
        "AsyncMock",
    ):
        # For mock objects, return empty dict to avoid accessing dynamic attributes
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

        # Handle Gemini ModalityTokenCount objects
        if type(data).__name__ == "ModalityTokenCount":
            try:
                return {
                    "modality": getattr(data, "modality", None),
                    "token_count": getattr(data, "token_count", None),
                }
            except (AttributeError, TypeError):
                # If we can't access the attributes, fall back to string representation
                return str(data)

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
    # Mock objects are always unsafe due to dynamic attribute creation
    if hasattr(obj, "_mock_name") or type(obj).__name__ in (
        "Mock",
        "MagicMock",
        "AsyncMock",
    ):
        return True

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
    """Normalize Gemini usage data to match server schema expectations.

    Handles both camelCase and snake_case field names, and includes all
    available usage fields from the Gemini API including caching, thinking,
    and tool usage tokens.
    """
    if usage is None:
        return {}

    # Convert to dict if it's an object
    if not isinstance(usage, Mapping):
        usage = _coerce_mapping(usage)

    if not isinstance(usage, dict):
        return {}

    # Map both camelCase and snake_case to standardized camelCase output
    # Core token counts
    normalized = {
        "promptTokenCount": _get_field_value(
            usage, "promptTokenCount", "prompt_token_count"
        ),
        "candidatesTokenCount": _get_field_value(
            usage, "candidatesTokenCount", "candidates_token_count"
        ),
        "totalTokenCount": _get_field_value(
            usage, "totalTokenCount", "total_token_count"
        ),
        # Caching and advanced features
        "cachedContentTokenCount": _get_field_value(
            usage, "cachedContentTokenCount", "cached_content_token_count"
        ),
        "toolUsePromptTokenCount": _get_field_value(
            usage, "toolUsePromptTokenCount", "tool_use_prompt_token_count"
        ),
        "thoughtsTokenCount": _get_field_value(
            usage, "thoughtsTokenCount", "thoughts_token_count"
        ),
    }

    # Handle detailed breakdowns (arrays/objects) with special processing for ModalityTokenCount
    def _process_modality_details(details):
        if not details:
            return None
        if not isinstance(details, (list, tuple)):
            return details

        # Process each item in the details array
        processed = []
        for item in details:
            if type(item).__name__ == "ModalityTokenCount":
                try:
                    processed.append(
                        {
                            "modality": getattr(item, "modality", None),
                            "token_count": getattr(item, "token_count", None),
                        }
                    )
                except (AttributeError, TypeError):
                    processed.append(str(item))
            else:
                processed.append(item)
        return processed

    # Process token details arrays
    prompt_details = _get_field_value(
        usage, "promptTokensDetails", "prompt_tokens_details"
    )
    candidates_details = _get_field_value(
        usage, "candidatesTokensDetails", "candidates_tokens_details"
    )
    cache_details = _get_field_value(
        usage, "cacheTokensDetails", "cache_tokens_details"
    )

    if prompt_details is not None:
        normalized["promptTokensDetails"] = _process_modality_details(prompt_details)
    if candidates_details is not None:
        normalized["candidatesTokensDetails"] = _process_modality_details(
            candidates_details
        )
    if cache_details is not None:
        normalized["cacheTokensDetails"] = _process_modality_details(cache_details)

    # Filter out None values
    return {k: v for k, v in normalized.items() if v is not None}


def _get_field_value(obj: Any, camel_case: str, snake_case: str) -> Any:
    """Get field value trying both camelCase and snake_case variants."""
    if hasattr(obj, camel_case):
        value = getattr(obj, camel_case)
        if value is not None:
            return value
    if hasattr(obj, snake_case):
        value = getattr(obj, snake_case)
        if value is not None:
            return value
    if isinstance(obj, Mapping):
        value = obj.get(camel_case)
        if value is not None:
            return value
        value = obj.get(snake_case)
        if value is not None:
            return value
    return None


def _coerce_mapping(obj: Any) -> dict:
    """Best-effort convert SDK objects to plain dicts (only for known fields)."""
    if isinstance(obj, Mapping):
        return dict(obj)
    # Fallback—pull known attributes if present
    out = {}
    for name in (
        "promptTokenCount",
        "candidatesTokenCount",
        "totalTokenCount",
        "cachedContentTokenCount",
        "toolUsePromptTokenCount",
        "thoughtsTokenCount",
        "promptTokensDetails",
        "candidatesTokensDetails",
        "cacheTokensDetails",
        "prompt_token_count",
        "candidates_token_count",
        "total_token_count",
        "cached_content_token_count",
        "tool_use_prompt_token_count",
        "thoughts_token_count",
        "prompt_tokens_details",
        "candidates_tokens_details",
        "cache_tokens_details",
    ):
        v = getattr(obj, name, None)
        if v is not None:
            out[name] = v
    return out


def get_usage_from_response(response: Any, api_id: str) -> dict[str, Any]:
    """Return JSON-serializable usage info from an API response."""
    usage: Any = None
    if api_id in {"openai_chat", "openai_responses", "fireworks-ai"}:
        usage = getattr(response, "usage", None)
    elif api_id == "anthropic":
        usage = (
            response if not hasattr(response, "usage") else getattr(response, "usage")
        )
    elif api_id == "amazon-bedrock":
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
        # Try both camelCase and snake_case variants
        usage = getattr(response, "usageMetadata", None) or getattr(
            response, "usage_metadata", None
        )
        # If found, normalize to our standardized format
        if usage is not None:
            return _normalize_gemini_usage(usage)
    return _to_serializable_dict(usage)


def get_streaming_usage_from_response(chunk: Any, api_id: str) -> dict[str, Any]:
    """Extract usage information from streaming response chunks."""
    usage: Any = None
    if api_id in {"openai_chat", "openai_responses", "fireworks-ai"}:
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

    elif api_id == "amazon-bedrock":
        if isinstance(chunk, Mapping):
            if "metadata" in chunk and "usage" in chunk["metadata"]:
                usage = chunk["metadata"]["usage"]
            elif "usage" in chunk:
                usage = chunk["usage"]

    elif api_id == "gemini":
        # Try multiple locations for usage metadata, both camelCase and snake_case
        meta = None

        # 1) direct on the event (both variants)
        meta = getattr(chunk, "usageMetadata", None) or getattr(
            chunk, "usage_metadata", None
        )

        # 2) sometimes nested under .model_response
        if meta is None and hasattr(chunk, "model_response"):
            meta = getattr(chunk.model_response, "usageMetadata", None) or getattr(
                chunk.model_response, "usage_metadata", None
            )

        # 3) dict-like fallback
        if meta is None and isinstance(chunk, Mapping):
            model_resp = chunk.get("model_response")
            meta = (
                chunk.get("usageMetadata")
                or chunk.get("usage_metadata")
                or (model_resp or {}).get("usageMetadata")
                or (model_resp or {}).get("usage_metadata")
                if isinstance(model_resp, Mapping)
                else None
            )

        # If found, normalize to our standardized format
        if meta is not None:
            return _normalize_gemini_usage(meta)

    return _to_serializable_dict(usage)


__all__ = [
    "get_usage_from_response",
    "get_streaming_usage_from_response",
]
