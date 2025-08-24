from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ..client.exceptions import UsageLimitExceeded
from ..config_manager import ConfigManager
from ..ini_manager import IniManager
from ..logger import create_logger


class DeliveryType(str, Enum):
    IMMEDIATE = "immediate"
    PERSISTENT_QUEUE = "persistent_queue"


@dataclass
class DeliveryConfig:
    """Common configuration shared by delivery implementations."""

    ini_manager: IniManager
    aicm_api_key: str | None = None
    aicm_api_base: str | None = None
    aicm_api_url: str | None = None
    timeout: float = 10.0
    transport: httpx.BaseTransport | None = None
    log_file: str | None = None
    log_level: str | None = None
    # For immediate delivery post-send wait before checking limits
    immediate_pause_seconds: float = 5.0


class Delivery(ABC):
    """Abstract base class for tracker delivery mechanisms."""

    def __init__(
        self,
        config: DeliveryConfig,
        *,
        endpoint: str = "/track",
        body_key: str = "tracked",
        logger: logging.Logger | None = None,
    ) -> None:
        if config.ini_manager is None:
            raise ValueError("ini_manager must be provided")
        self.ini_manager = config.ini_manager
        self.logger = logger or create_logger(
            self.__class__.__name__, config.log_file, config.log_level
        )
        self.api_key = config.aicm_api_key or os.getenv("AICM_API_KEY")
        self.api_base = config.aicm_api_base or "https://aicostmanager.com"
        self.api_url = config.aicm_api_url or "/api/v1"
        self.timeout = config.timeout
        self._transport = config.transport
        self._client = httpx.Client(timeout=config.timeout, transport=config.transport)
        self._root = self.api_base.rstrip("/") + self.api_url.rstrip("/")
        self._endpoint = self._root + endpoint
        self._body_key = body_key
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "aicostmanager-python",
        }
        self.immediate_pause_seconds = getattr(config, "immediate_pause_seconds", 5.0)

    def _limits_enabled(self) -> bool:
        """Return ``True`` when triggered limits should be enforced."""
        val = self.ini_manager.get_option("tracker", "AICM_LIMITS_ENABLED", "false")
        return str(val).lower() in {"1", "true", "yes", "on"}

    def _post_with_retry(
        self, body: Dict[str, Any], *, max_attempts: int
    ) -> Dict[str, Any]:
        def _retryable(exc: Exception) -> bool:
            if isinstance(exc, httpx.HTTPStatusError):
                return exc.response is None or exc.response.status_code >= 500
            # Don't retry if client is closed - it won't recover
            if isinstance(exc, RuntimeError) and "client has been closed" in str(exc):
                return False
            return True

        for attempt in Retrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential_jitter(),
            retry=retry_if_exception(_retryable),
        ):
            with attempt:
                # Check if client is closed before attempting request
                if self._client.is_closed:
                    raise RuntimeError(
                        "HTTP client has been closed - cannot send request"
                    )
                resp = self._client.post(
                    self._endpoint, json=body, headers=self._headers
                )
                resp.raise_for_status()
                return resp.json()
        raise RuntimeError("unreachable")

    def _check_triggered_limits(self, payload: Dict[str, Any]) -> None:
        """Raise ``UsageLimitExceeded`` if ``payload`` matches a triggered limit.

        Uses a client-backed ConfigManager to ensure we can refresh and decode
        triggered limits when the server omits the public key from inline responses.
        """
        # Use file-backed ConfigManager to avoid incidental GETs that could stale/clear state
        cfg = ConfigManager(ini_path=self.ini_manager.ini_path, load=False)
        service_key = payload.get("service_key")
        vendor = service_id = None
        if service_key and "::" in service_key:
            vendor, service_id = service_key.split("::", 1)
        elif service_key:
            service_id = service_key
        client_customer_key = payload.get("client_customer_key")
        # Prefer matching on full service_key; fall back to service_id/vendor filtering
        limits = cfg.get_triggered_limits(
            service_id=service_id,
            service_vendor=vendor,
            client_customer_key=client_customer_key,
        )
        if service_key:
            limits = [
                l for l in limits if getattr(l, "service_key", None) == service_key
            ]
        # Match against the API key ID used by the server (typically the UUID
        # suffix of the API key string "....<uuid>"). Fallback to the full
        # key if no dot is present for compatibility with older formats.
        api_key_id = None
        if self.api_key:
            api_key_id = (
                self.api_key.split(".")[-1] if "." in self.api_key else self.api_key
            )
        if api_key_id:
            limits = [l for l in limits if l.api_key_id == api_key_id]
        if limits:
            # Recompute with latest state (limits may have been updated by recent track)
            limits = cfg.get_triggered_limits(
                service_id=service_id,
                service_vendor=vendor,
                client_customer_key=client_customer_key,
            )
            if service_key:
                limits = [
                    l for l in limits if getattr(l, "service_key", None) == service_key
                ]
            if api_key_id:
                limits = [l for l in limits if l.api_key_id == api_key_id]
            if limits:
                raise UsageLimitExceeded(limits)

    @abstractmethod
    def _enqueue(self, payload: Dict[str, Any]) -> Any:
        """Implementation-specific enqueue logic."""

    def enqueue(self, payload: Dict[str, Any]) -> Any:
        """Queue ``payload`` for background delivery and enforce triggered limits."""
        if isinstance(self, QueueDelivery):
            result = self._enqueue(payload)
            if self._limits_enabled():
                self._check_triggered_limits(
                    payload
                )  # This check happens AFTER enqueue
            return result

        result = self._enqueue(payload)
        if self._limits_enabled():
            self._check_triggered_limits(payload)
        return result

    def deliver(self, body: Dict[str, Any]) -> None:
        """Queue payloads from a pre-built request body."""
        for payload in body.get(self._body_key, []):
            self.enqueue(payload)

    def stop(self) -> None:  # pragma: no cover - default no-op
        """Shutdown any background resources."""
        return None


@dataclass
class QueueItem:
    payload: Dict[str, Any]
    id: Optional[int] = None
    retry_count: int = 0


class QueueWorker(ABC):
    """Abstract helper for queue based deliveries."""

    @abstractmethod
    def get_batch(self, max_batch_size: int, *, block: bool = True) -> List[QueueItem]:
        """Return up to ``max_batch_size`` items for processing."""

    def acknowledge(
        self, items: List[QueueItem]
    ) -> None:  # pragma: no cover - default no-op
        return None

    def reschedule(self, item: QueueItem) -> None:  # pragma: no cover - default no-op
        return None

    def queued(self) -> int:  # pragma: no cover - default no-op
        return 0


class QueueDelivery(Delivery, QueueWorker):
    """Base class for threaded queue based deliveries."""

    def __init__(
        self,
        config: DeliveryConfig,
        *,
        batch_interval: float = 0.5,
        max_batch_size: int = 1000,
        max_attempts: int = 5,
        max_retries: int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self.batch_interval = batch_interval
        self.max_batch_size = max_batch_size
        self.max_attempts = max_attempts
        self.max_retries = max_retries
        self._total_sent = 0
        self._total_failed = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _process_batch(self, batch: List[QueueItem]) -> None:
        payloads = [item.payload for item in batch]
        body = {self._body_key: payloads}
        try:
            data = self._post_with_retry(body, max_attempts=self.max_attempts)
            if self._limits_enabled() and isinstance(data, dict):
                tl_data = data.get("triggered_limits")
                if tl_data:
                    # Use a ConfigManager that preserves existing INI settings
                    cfg = ConfigManager(ini_path=self.ini_manager.ini_path, load=True)
                    try:
                        cfg.write_triggered_limits(tl_data)
                    except Exception as exc:  # pragma: no cover - network failures
                        self.logger.error("Triggered limits update failed: %s", exc)
        except Exception as exc:  # pragma: no cover - network failures
            self.logger.error("Delivery failed: %s", exc)
            for item in batch:
                item.retry_count += 1
                self.reschedule(item)
                self._total_failed += 1
        else:
            self.acknowledge(batch)
            self._total_sent += len(batch)

    def _run(self) -> None:
        while not self._stop.is_set():
            batch = self.get_batch(self.max_batch_size, block=True)
            if not batch:
                continue
            self._process_batch(batch)
        while True:
            batch = self.get_batch(self.max_batch_size, block=False)
            if not batch:
                break
            self._process_batch(batch)
        self._client.close()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()
        super().stop()

    def stats(self) -> Dict[str, Any]:
        return {
            "queued": self.queued(),
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
        }
