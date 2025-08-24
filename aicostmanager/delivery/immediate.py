from __future__ import annotations

from typing import Any, Dict

from ..client.exceptions import NoCostsTrackedException, UsageLimitExceeded
from ..config_manager import ConfigManager
from .base import Delivery, DeliveryConfig, DeliveryType


class ImmediateDelivery(Delivery):
    """Synchronous delivery using direct HTTP requests with retries."""

    type = DeliveryType.IMMEDIATE

    def __init__(self, config: DeliveryConfig) -> None:
        super().__init__(config)

    def _enqueue(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = {self._body_key: [payload]}
        try:
            data = self._post_with_retry(body, max_attempts=3)
            tl_data = data.get("triggered_limits", {}) if isinstance(data, dict) else {}
            
            # Always create a ConfigManager for potential limit checking
            cfg = ConfigManager(ini_path=self.ini_manager.ini_path, load=True)
            
            if tl_data:
                # Write triggered limits to INI if we received any
                try:
                    cfg.write_triggered_limits(tl_data)
                except Exception as exc:  # pragma: no cover
                    self.logger.error("Failed to persist triggered limits: %s", exc)
            
            result = {}
            if isinstance(data, dict):
                results = data.get("results") or []
                if results:
                    result = results[0] or {}
            cost_events = (
                result.get("cost_events") if isinstance(result, dict) else None
            )
            if not cost_events:
                raise NoCostsTrackedException()
            
            # Proactively raise on this call if the server indicates a limit was triggered
            # and limits are enabled
            if self._limits_enabled() and isinstance(tl_data, dict):
                # Use the ConfigManager instance we created above
                cfg_limits = cfg
                request_service_key = payload.get("service_key")
                client_customer_key = payload.get("client_customer_key")
                vendor = service_id = None
                if isinstance(request_service_key, str) and "::" in request_service_key:
                    vendor, service_id = request_service_key.split("::", 1)
                elif isinstance(request_service_key, str):
                    service_id = request_service_key
                limits = cfg_limits.get_triggered_limits(
                    service_id=service_id,
                    service_vendor=vendor,
                    client_customer_key=client_customer_key,
                )
                if request_service_key:
                    limits = [
                        l
                        for l in limits
                        if getattr(l, "service_key", None) == request_service_key
                    ]
                api_key_id = (
                    self.api_key.split(".")[-1]
                    if self.api_key and "." in self.api_key
                    else self.api_key
                )
                if api_key_id:
                    limits = [l for l in limits if l.api_key_id == api_key_id]
                if limits:
                    raise UsageLimitExceeded(limits)
            return {"result": result, "triggered_limits": tl_data}
        except Exception as exc:
            self.logger.exception("Immediate delivery failed: %s", exc)
            raise

    def stop(self) -> None:  # pragma: no cover - nothing to cleanup
        self._client.close()
