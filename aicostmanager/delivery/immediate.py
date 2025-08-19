from __future__ import annotations

from typing import Any, Dict

from .base import Delivery, DeliveryConfig, DeliveryType


class ImmediateDelivery(Delivery):
    """Synchronous delivery using direct HTTP requests with retries."""

    type = DeliveryType.IMMEDIATE

    def __init__(self, config: DeliveryConfig) -> None:
        super().__init__(config)

    def _enqueue(self, payload: Dict[str, Any]) -> None:
        body = {self._body_key: [payload]}
        try:
            self._post_with_retry(body, max_attempts=3)
            self._refresh_triggered_limits()
        except Exception as exc:
            self.logger.exception("Immediate delivery failed: %s", exc)
            raise

    def stop(self) -> None:  # pragma: no cover - nothing to cleanup
        self._client.close()
