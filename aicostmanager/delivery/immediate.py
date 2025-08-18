from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from .base import Delivery
from ..ini_manager import IniManager


class ImmediateDelivery(Delivery):
    """Synchronous delivery using direct HTTP requests with retries."""

    def __init__(
        self,
        *,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        ini_manager: IniManager | None = None,
        log_file: str | None = None,
        log_level: str | None = None,
    ) -> None:
        super().__init__(
            ini_manager=ini_manager,
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            timeout=timeout,
            transport=transport,
            log_file=log_file,
            log_level=log_level,
        )

    def enqueue(self, payload: Dict[str, Any]) -> None:
        body = {self._body_key: [payload]}
        try:
            self._post_with_retry(body, max_attempts=3)
        except Exception as exc:
            self.logger.exception("Immediate delivery failed: %s", exc)
            raise

    def stop(self) -> None:  # pragma: no cover - nothing to cleanup
        self._client.close()
