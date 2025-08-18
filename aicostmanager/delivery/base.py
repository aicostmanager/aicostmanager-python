from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict

import httpx
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from ..ini_manager import IniManager


class DeliveryType(str, Enum):
    IMMEDIATE = "immediate"
    MEM_QUEUE = "mem_queue"
    PERSISTENT_QUEUE = "persistent_queue"


class Delivery(ABC):
    """Abstract base class for tracker delivery mechanisms."""

    def __init__(
        self,
        *,
        ini_manager: IniManager | None = None,
        aicm_api_key: str | None = None,
        aicm_api_base: str | None = None,
        aicm_api_url: str | None = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        endpoint: str = "/track",
        body_key: str = "tracked",
        log_file: str | None = None,
        log_level: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.ini_manager = ini_manager or IniManager()
        self.logger = logger or self.ini_manager.create_logger(
            self.__class__.__name__,
            log_file,
            log_level,
            "AICM_DELIVERY_LOG_FILE",
            "AICM_DELIVERY_LOG_LEVEL",
        )
        self.api_key = aicm_api_key or os.getenv("AICM_API_KEY")
        self.api_base = aicm_api_base or os.getenv("AICM_API_BASE", "https://aicostmanager.com")
        self.api_url = aicm_api_url or os.getenv("AICM_API_URL", "/api/v1")
        self.timeout = timeout
        self._transport = transport
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._endpoint = self.api_base.rstrip("/") + self.api_url.rstrip("/") + endpoint
        self._body_key = body_key
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "aicostmanager-python",
        }

    def _post_with_retry(self, body: Dict[str, Any], *, max_attempts: int) -> httpx.Response:
        def _retryable(exc: Exception) -> bool:
            if isinstance(exc, httpx.HTTPStatusError):
                return exc.response is None or exc.response.status_code >= 500
            return True

        for attempt in Retrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential_jitter(),
            retry=retry_if_exception(_retryable),
        ):
            with attempt:
                resp = self._client.post(self._endpoint, json=body, headers=self._headers)
                resp.raise_for_status()
                return resp
        raise RuntimeError("unreachable")

    @abstractmethod
    def enqueue(self, payload: Dict[str, Any]) -> None:
        """Queue ``payload`` for background delivery."""

    def stop(self) -> None:  # pragma: no cover - default no-op
        """Shutdown any background resources."""
        return None
