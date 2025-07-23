"""Light weight wrapper that coordinates a client with :class:`UniversalExtractor`."""

from __future__ import annotations

from typing import Any, List, Optional

from .client import CostManagerClient
from .config_manager import Config, CostManagerConfig
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
        delivery: ResilientDelivery | None = None,
        delivery_queue_size: int = 1000,
        delivery_max_retries: int = 5,
        delivery_timeout: float = 10.0,
    ) -> None:
        self.client = client
        self.cm_client = CostManagerClient(
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
        )
        self.config_manager = CostManagerConfig(self.cm_client)
        self.api_id = client.__class__.__name__.lower()
        self.configs: List[Config] = self.config_manager.get_config(self.api_id)
        self.extractor = UniversalExtractor(self.configs)
        self.tracked_payloads: list[dict[str, Any]] = []

        if delivery is not None:
            self.delivery = delivery
        else:
            self.delivery = get_global_delivery(
                self.cm_client,
                max_retries=delivery_max_retries,
                queue_size=delivery_queue_size,
                timeout=delivery_timeout,
            )

    # ------------------------------------------------------------
    # attribute proxying
    # ------------------------------------------------------------
    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.client, name)

        if callable(attr):

            def wrapper(*args, **kwargs):
                response = attr(*args, **kwargs)
                payloads = self.extractor.process_call(
                    name, args, kwargs, response, client=self.client
                )
                if payloads:
                    self.tracked_payloads.extend(payloads)
                    for payload in payloads:
                        self.delivery.deliver({"usage_records": [payload]})
                return response

            return wrapper
        else:
            # For non-callable attributes, wrap them with a nested tracker
            # to handle cases like client.chat.completions.create()
            return NestedAttributeWrapper(attr, self, name)

    def get_tracked_payloads(self) -> list[dict[str, Any]]:
        """Return a copy of payloads generated so far."""

        return list(self.tracked_payloads)

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
                response = attr(*args, **kwargs)
                payloads = self._parent_manager.extractor.process_call(
                    full_path,
                    args,
                    kwargs,
                    response,
                    client=self._parent_manager.client,
                )
                if payloads:
                    self._parent_manager.tracked_payloads.extend(payloads)
                    for payload in payloads:
                        self._parent_manager.delivery.deliver(
                            {"usage_records": [payload]}
                        )
                return response

            return wrapper
        else:
            # Continue wrapping for deeper nesting
            return NestedAttributeWrapper(attr, self._parent_manager, full_path)
