from __future__ import annotations

from typing import Any, Dict, Optional

import os
import httpx
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from .base import Delivery


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
        log_file: str | None = None,
        log_level: str | None = None,
    ) -> None:
        super().__init__(log_file=log_file, log_level=log_level)
        self.api_key = aicm_api_key or os.getenv("AICM_API_KEY")
        self.api_base = aicm_api_base or os.getenv("AICM_API_BASE", "https://aicostmanager.com")
        self.api_url = aicm_api_url or os.getenv("AICM_API_URL", "/api/v1")
        self.timeout = timeout
        self._transport = transport
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._endpoint = self.api_base.rstrip("/") + self.api_url.rstrip("/") + "/track"
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "aicostmanager-python",
        }

    def enqueue(self, payload: Dict[str, Any]) -> None:
        body = {"tracked": [payload]}

        def _retryable(exc: Exception) -> bool:
            if isinstance(exc, httpx.HTTPStatusError):
                return exc.response is None or exc.response.status_code >= 500
            return True

        try:
            for attempt in Retrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential_jitter(),
                retry=retry_if_exception(_retryable),
            ):
                with attempt:
                    resp = self._client.post(self._endpoint, json=body, headers=self._headers)
                    resp.raise_for_status()
                    return None
        except Exception as exc:
            self.logger.exception("Immediate delivery failed: %s", exc)
            raise

    def stop(self) -> None:  # pragma: no cover - nothing to cleanup
        self._client.close()
