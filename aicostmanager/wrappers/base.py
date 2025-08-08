"""Shared base class for cost tracking wrappers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..client import CostManagerClient, UsageLimitExceeded
from ..config_manager import Config, CostManagerConfig, TriggeredLimit
from ..universal_extractor import UniversalExtractor


class BaseCostManager:
    """Common initialization and helpers for tracking wrappers."""

    def __init__(
        self,
        client: Any,
        config_client: CostManagerClient,
        cm_client: CostManagerClient,
        *,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        delivery: Any = None,
    ) -> None:
        self.client = client
        self.cm_client = cm_client
        self.config_manager = CostManagerConfig(config_client)
        self.api_id = client.__class__.__module__.lower()
        self.configs: List[Config] = self.config_manager.get_config(self.api_id)
        self.extractor = UniversalExtractor(self.configs)
        self.tracked_payloads: List[dict[str, Any]] = []
        self.triggered_limits: List[TriggeredLimit] = []
        self.client_customer_key = client_customer_key
        self.context = context
        self.delivery = delivery

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

    def get_tracked_payloads(self) -> List[dict[str, Any]]:
        return list(self.tracked_payloads)

    # streaming helpers -------------------------------------------------
    def _is_streaming(self, result: Any) -> bool:
        return (
            self._is_streaming_type(result)
            or self._appears_to_be_stream(result)
            or self._has_streaming_interface(result)
            or self._is_bedrock_streaming(result)
        )

    def _is_streaming_type(self, result: Any) -> bool:
        import inspect
        from typing import AsyncGenerator, AsyncIterator, Generator, Iterator

        if isinstance(result, (Iterator, AsyncIterator, Generator, AsyncGenerator)):
            return True
        if inspect.isgenerator(result) or inspect.isasyncgen(result):
            return True
        return False

    def _appears_to_be_stream(self, result: Any) -> bool:
        class_name = type(result).__name__.lower()
        if any(indicator in class_name for indicator in ["stream", "iterator", "chunk"]):
            return True
        if hasattr(result, "__iter__") and hasattr(result, "__next__"):
            return True
        if hasattr(result, "__aiter__") and hasattr(result, "__anext__"):
            return True
        return False

    def _has_streaming_interface(self, result: Any) -> bool:
        streaming_methods = [
            "read",
            "readline",
            "__stream__",
            "iter_lines",
            "iter_content",
        ]
        return any(hasattr(result, method) for method in streaming_methods)

    def _is_bedrock_streaming(self, result: Any) -> bool:
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
