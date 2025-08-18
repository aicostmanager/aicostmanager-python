from __future__ import annotations

from typing import Any, Dict

from ..client import CostManagerClient
from ..limits import TriggeredLimitManager
from .base import Delivery, DeliveryConfig, DeliveryType


class ImmediateDelivery(Delivery):
    """Synchronous delivery using direct HTTP requests with retries."""

    type = DeliveryType.IMMEDIATE

    def __init__(self, config: DeliveryConfig) -> None:
        super().__init__(config)

    def enqueue(self, payload: Dict[str, Any]) -> None:
        body = {self._body_key: [payload]}
        try:
            self._post_with_retry(body, max_attempts=3)
            client: CostManagerClient | None = None
            try:
                client = CostManagerClient(
                    aicm_api_key=self.api_key,
                    aicm_api_base=self.api_base,
                    aicm_api_url=self.api_url,
                    aicm_ini_path=self.ini_manager.ini_path,
                )
                TriggeredLimitManager(client).update_triggered_limits()
            except Exception as exc:
                self.logger.error("Triggered limits update failed: %s", exc)
            finally:
                if client is not None:
                    client.close()
        except Exception as exc:
            self.logger.exception("Immediate delivery failed: %s", exc)
            raise

    def stop(self) -> None:  # pragma: no cover - nothing to cleanup
        self._client.close()
