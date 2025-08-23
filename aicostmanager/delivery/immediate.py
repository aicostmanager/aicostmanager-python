from __future__ import annotations

from typing import Any, Dict

from ..config_manager import ConfigManager
from ..client.exceptions import NoCostsTrackedException
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
            if tl_data:
                cfg = ConfigManager(ini_path=self.ini_manager.ini_path, load=False)
                try:
                    cfg.write_triggered_limits(tl_data)
                except Exception as exc:  # pragma: no cover
                    self.logger.error("Failed to persist triggered limits: %s", exc)
            result = {}
            if isinstance(data, dict):
                results = data.get("results") or []
                if results:
                    result = results[0] or {}
            cost_events = result.get("cost_events") if isinstance(result, dict) else None
            if not cost_events:
                raise NoCostsTrackedException()
            return {"result": result, "triggered_limits": tl_data}
        except Exception as exc:
            self.logger.exception("Immediate delivery failed: %s", exc)
            raise

    def stop(self) -> None:  # pragma: no cover - nothing to cleanup
        self._client.close()
