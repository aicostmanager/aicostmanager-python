"""Generic extraction helpers used for tracking API usage.

This module exposes :class:`UniversalExtractor` which is a very small
subset of the much more feature rich implementation that lives in the
``sdks/scratch_examples`` directory.  The goal of this light weight
version is simply to demonstrate how configuration objects can drive
extraction of request/response data from any wrapped API client.

The extractor is intentionally conservative and only implements the
behaviour required by the accompanying tests.  It is heavily commented
so that consumers can extend the logic for their own needs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import ParseResult

from .config_manager import Config


class UniversalExtractor:
    """Extract data from API calls based on :class:`Config` objects."""

    def __init__(self, configs: Iterable[Config]):
        # ``configs`` is expected to be an iterable of ``Config`` instances
        # returned from :class:`CostManagerConfig`.  Only the
        # ``handling_config`` attribute of each object is used by this
        # lightweight extractor.
        self.configs = list(configs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def process_call(
        self,
        method_name: str,
        args: tuple,
        kwargs: dict,
        response: Any,
        *,
        client: Any,
    ) -> list[dict[str, Any]]:
        """Return tracking payloads for ``method_name``.

        The extractor will iterate through all loaded configs and, when a
        config declares the ``method_name`` in ``tracked_methods``, a
        payload will be built describing the call.  The returned list may
        therefore contain zero or more payload dictionaries.
        """

        payloads: list[dict[str, Any]] = []
        for cfg in self.configs:
            if not self._method_is_tracked(cfg, method_name):
                continue
            try:
                tracking = self._build_tracking_data(
                    cfg, method_name, args, kwargs, response, client
                )
                payload = self._build_payload(cfg, tracking)
                payloads.append(payload)
            except Exception as exc:  # pragma: no cover - safety
                logging.error("failed to build payload: %s", exc)
        return payloads

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _method_is_tracked(self, cfg: Config, method_name: str) -> bool:
        methods = cfg.handling_config.get("tracked_methods", [])
        return any(method_name.endswith(m) for m in methods)

    def _build_tracking_data(
        self,
        cfg: Config,
        method_name: str,
        args: tuple,
        kwargs: dict,
        response: Any,
        client: Any,
    ) -> dict[str, Any]:
        """Create the base tracking dictionary for a single config."""
        tracking: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "method": method_name,
            "config_identifier": cfg.config_id,
            "request_data": self._extract_request_fields(cfg, kwargs),
            "response_data": self._extract_response_fields(cfg, response),
            "client_data": self._extract_client_fields(cfg, client),
        }
        tracking["usage_data"] = self._extract_usage_data(cfg, tracking)
        return tracking

    # Extraction helper methods
    def _extract_request_fields(self, cfg: Config, kwargs: dict) -> dict[str, Any]:
        fields = cfg.handling_config.get("request_fields", [])
        data: dict[str, Any] = {}
        for field in fields:
            if field in kwargs:
                data[field] = kwargs[field]
        return data

    def _extract_response_fields(self, cfg: Config, response: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field in cfg.handling_config.get("response_fields", []):
            path = field["path"] if isinstance(field, dict) else field
            key = field.get("key") if isinstance(field, dict) else path.split(".")[-1]
            value = self._get_nested_value(response, path)
            if value is not None:
                result[key] = value
        return result

    def _extract_client_fields(self, cfg: Config, client: Any) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, spec in cfg.handling_config.get("client_fields", {}).items():
            path = spec.get("path", name) if isinstance(spec, dict) else spec
            out[name] = self._get_nested_value(client, path)
        return out

    def _extract_usage_data(
        self, cfg: Config, tracking: dict[str, Any]
    ) -> dict[str, Any]:
        mapping = cfg.handling_config.get("payload_mapping", {})
        usage_key = mapping.get("usage")
        if not usage_key:
            return {}
        return self._get_nested_value(tracking, usage_key) or {}

    def _build_payload(self, cfg: Config, tracking: dict[str, Any]) -> dict[str, Any]:
        mapping = cfg.handling_config.get("payload_mapping", {})
        payload: dict[str, Any] = {}
        for key, path in mapping.items():
            value = self._get_nested_value(tracking, path)
            # Ensure the value is JSON-serializable
            payload[key] = self._make_json_serializable(value)
        static_fields = cfg.handling_config.get("static_payload_fields", {})
        payload.update(static_fields)

        # Fix field name mismatches between config and API expectations
        api_payload = self._translate_to_api_format(payload)
        return api_payload

    def _translate_to_api_format(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Translate config field names to API field names."""
        api_payload = {}

        # Field name mappings from config to API
        field_mappings = {
            "config": "config_id",
            "model_id": "service_id",
        }

        for key, value in payload.items():
            # Use mapped field name if it exists, otherwise use original
            api_key = field_mappings.get(key, key)
            api_payload[api_key] = value

        # Ensure timestamp is a string in ISO format (without trailing Z)
        if "timestamp" in api_payload:
            if isinstance(api_payload["timestamp"], (int, float)):
                # Convert Unix timestamp to ISO string
                from datetime import datetime, timezone

                dt = datetime.fromtimestamp(api_payload["timestamp"], tz=timezone.utc)
                api_payload["timestamp"] = dt.isoformat(timespec="microseconds")
            elif isinstance(api_payload["timestamp"], str) and api_payload[
                "timestamp"
            ].endswith("Z"):
                # Remove trailing Z from ISO string
                api_payload["timestamp"] = api_payload["timestamp"][:-1]

        return api_payload

    def _make_json_serializable(self, value: Any) -> Any:
        """Convert complex objects to JSON-serializable representations."""
        if value is None:
            return None

        # Handle URLs
        if hasattr(value, "__class__") and "URL" in str(type(value)):
            return str(value)

        # Handle ParseResult (urllib.parse)
        if isinstance(value, ParseResult):
            return value.geturl()

        # Handle objects with model_dump (Pydantic models)
        if hasattr(value, "model_dump"):
            return value.model_dump()

        # Handle objects with dict() method
        if hasattr(value, "dict") and callable(getattr(value, "dict")):
            return value.dict()

        # Handle objects with __dict__ attribute
        if hasattr(value, "__dict__") and not isinstance(
            value, (str, int, float, bool, list, dict)
        ):
            return value.__dict__

        # Handle dictionaries recursively
        if isinstance(value, dict):
            return {k: self._make_json_serializable(v) for k, v in value.items()}

        # Handle lists/tuples recursively
        if isinstance(value, (list, tuple)):
            return [self._make_json_serializable(item) for item in value]

        # Basic types are already JSON-serializable
        if isinstance(value, (str, int, float, bool)):
            return value

        # Fallback: convert to string
        return str(value)

    # utility -----------------------------------------------------------
    def _get_nested_value(self, obj: Any, path: str) -> Any:
        """Resolve ``path`` (dot notation) against ``obj``."""
        try:
            parts = [p for p in path.split(".") if p]
            cur = obj
            for part in parts:
                if cur is None:
                    return None
                if isinstance(cur, dict):
                    cur = cur.get(part)
                else:
                    cur = getattr(cur, part, None)
            return cur
        except Exception:  # pragma: no cover - safety
            return None
