from __future__ import annotations

from typing import Any, Dict, Iterable, Tuple


def _to_dict(obj: Any) -> Dict[str, Any]:
    """Best-effort conversion of ``obj`` to a plain dictionary."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    for attr in ("model_dump", "to_dict", "dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                data = fn()  # type: ignore[call-arg]
                if isinstance(data, dict):
                    return data
            except Exception:  # pragma: no cover - safety
                pass
    try:
        return dict(obj)  # type: ignore[arg-type]
    except Exception:  # pragma: no cover - safety
        return {}


def extract_usage(response: Any) -> Dict[str, Any]:
    """Extract usage information from ``response`` if present."""
    if response is None:
        return {}

    # Handle objects with common usage attributes
    for attr in ("usage", "usage_metadata", "response_metadata"):
        data = _to_dict(getattr(response, attr, None))
        if data:
            # Some providers nest usage within metadata
            if "usage" in data and not {"input_tokens", "output_tokens"} & data.keys():
                nested = _to_dict(data.get("usage"))
                if nested:
                    return nested
            return data

    # Handle dictionary responses
    if isinstance(response, dict):
        for key in ("usage", "usageMetadata"):
            data = _to_dict(response.get(key))
            if data:
                return data
        metadata = response.get("metadata")
        if isinstance(metadata, dict):
            for key in ("usage", "usageMetadata"):
                data = _to_dict(metadata.get(key))
                if data:
                    return data
    return {}


def extract_stream_usage(stream: Iterable[Any]) -> Tuple[Dict[str, Any], Any]:
    """Consume a streaming iterator and return ``(usage, final_item)``."""
    final: Any | None = None
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


__all__ = ["extract_usage", "extract_stream_usage"]
