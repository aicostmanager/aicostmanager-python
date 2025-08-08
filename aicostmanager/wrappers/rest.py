"""Wrappers for generic REST clients using requests or httpx."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
import requests

from .client import AsyncResilientDelivery
from ..client import (
    AsyncCostManagerClient,
    CostManagerClient,
    UsageLimitExceeded,
)
from ..config_manager import Config, CostManagerConfig, TriggeredLimit
from ..delivery import ResilientDelivery, get_global_delivery
from ..universal_extractor import UniversalExtractor

_HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "head",
    "options",
    "request",
}


class RestUsageWrapper:
    """Wrap ``requests.Session`` to track REST API calls."""

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        *,
        base_url: str,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        aicm_ini_path: Optional[str] = None,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        delivery: ResilientDelivery | None = None,
        delivery_queue_size: int = 1000,
        delivery_max_retries: int = 5,
        delivery_timeout: float = 10.0,
        delivery_batch_interval: float | None = None,
        delivery_max_batch_size: int = 100,
        delivery_mode: str | None = None,
        delivery_on_full: str | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")
        parsed = urlparse(
            self.base_url if "//" in self.base_url else f"https://{self.base_url}"
        )
        self.hostname = parsed.netloc or parsed.path
        self.api_id = self.hostname.lower()
        self.client_customer_key = client_customer_key
        self.context = context

        self.cm_client = CostManagerClient(
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
        )
        self.config_manager = CostManagerConfig(self.cm_client)
        self.configs: List[Config] = self.config_manager.get_config(self.api_id)
        self.extractor = UniversalExtractor(self.configs)
        self.tracked_payloads: List[dict[str, Any]] = []
        self.triggered_limits: List[TriggeredLimit] = []

        if delivery is not None:
            self.delivery = delivery
        else:
            self.delivery = get_global_delivery(
                self.cm_client,
                max_retries=delivery_max_retries,
                queue_size=delivery_queue_size,
                timeout=delivery_timeout,
                batch_interval=delivery_batch_interval,
                max_batch_size=delivery_max_batch_size,
                delivery_mode=delivery_mode,
                on_full=delivery_on_full,
            )

    # ------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------
    def _refresh_limits(self, service_id: str) -> None:
        try:
            self.triggered_limits = self.config_manager.get_triggered_limits(
                service_id=service_id,
                client_customer_key=self.client_customer_key,
            )
            blocking = [l for l in self.triggered_limits if l.threshold_type == "limit"]
            if blocking:
                raise UsageLimitExceeded(blocking)
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

    def _full_url(self, url: str) -> str:
        if url.startswith("http"):
            return url
        return urljoin(self.base_url + "/", url.lstrip("/"))

    def _service_id(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.netloc}{parsed.path}"

    # ------------------------------------------------------------
    # main request method
    # ------------------------------------------------------------
    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        full = self._full_url(url)
        service_id = self._service_id(full)
        self._refresh_limits(service_id)
        resp = self.session.request(method, full, **kwargs)
        try:
            data = resp.json()
        except Exception:
            data = resp.text
        method_name = f"{method.upper()} {urlparse(full).path}"
        payloads = self.extractor.process_call(
            method_name,
            (),
            kwargs,
            data,
            client=self.session,
            is_streaming=False,
        )
        for payload in payloads:
            if "service_id" not in payload:
                payload["service_id"] = service_id
            self._augment_payload(payload)
        if payloads:
            self.tracked_payloads.extend(payloads)
            for p in payloads:
                self.delivery.deliver({"usage_records": [p]})
        return resp

    # ------------------------------------------------------------
    # attribute proxying
    # ------------------------------------------------------------
    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.session, name)
        if name.lower() in _HTTP_METHODS and callable(attr):

            def wrapper(*args, **kwargs):
                method = name if name != "request" else args[0]
                url = args[1] if name == "request" else args[0]
                return self.request(method, url, **kwargs)

            return wrapper
        return attr

    def get_tracked_payloads(self) -> List[dict[str, Any]]:
        return list(self.tracked_payloads)

    # ------------------------------------------------------------
    # delivery helpers
    # ------------------------------------------------------------
    def start_delivery(self) -> None:
        self.delivery.start()

    def stop_delivery(self) -> None:
        self.delivery.stop()

    def __enter__(self) -> "RestUsageWrapper":
        self.start_delivery()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop_delivery()


class AsyncRestUsageWrapper:
    """Async wrapper for ``httpx.AsyncClient`` to track REST calls."""

    def __init__(
        self,
        session: Optional[httpx.AsyncClient] = None,
        *,
        base_url: str,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        aicm_ini_path: Optional[str] = None,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        delivery: AsyncResilientDelivery | None = None,
        delivery_queue_size: int = 1000,
        delivery_max_retries: int = 5,
        delivery_timeout: float = 10.0,
    ) -> None:
        self.session = session or httpx.AsyncClient()
        self.base_url = base_url.rstrip("/")
        parsed = urlparse(
            self.base_url if "//" in self.base_url else f"https://{self.base_url}"
        )
        self.hostname = parsed.netloc or parsed.path
        self.api_id = self.hostname.lower()
        self.client_customer_key = client_customer_key
        self.context = context

        cfg_client = CostManagerClient(
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
        )
        self.cm_client = AsyncCostManagerClient(
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
        )
        self.config_manager = CostManagerConfig(cfg_client)
        self.configs: List[Config] = self.config_manager.get_config(self.api_id)
        cfg_client.close()
        self.extractor = UniversalExtractor(self.configs)
        self.tracked_payloads: List[dict[str, Any]] = []
        self.triggered_limits: List[TriggeredLimit] = []

        if delivery is not None:
            self.delivery = delivery
        else:
            self.delivery = AsyncResilientDelivery(
                self.cm_client.session,
                self.cm_client.api_root,
                max_retries=delivery_max_retries,
                queue_size=delivery_queue_size,
                timeout=delivery_timeout,
            )
        self.delivery.start()

    # helpers -----------------------------------------------------
    def _full_url(self, url: str) -> str:
        if url.startswith("http"):
            return url
        return urljoin(self.base_url + "/", url.lstrip("/"))

    def _service_id(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.netloc}{parsed.path}"

    def _refresh_limits(self, service_id: str) -> None:
        try:
            self.triggered_limits = self.config_manager.get_triggered_limits(
                service_id=service_id,
                client_customer_key=self.client_customer_key,
            )
            blocking = [l for l in self.triggered_limits if l.threshold_type == "limit"]
            if blocking:
                raise UsageLimitExceeded(blocking)
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

    # main request ------------------------------------------------
    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        full = self._full_url(url)
        service_id = self._service_id(full)
        self._refresh_limits(service_id)
        resp = await self.session.request(method, full, **kwargs)
        try:
            data = resp.json()
        except Exception:
            data = resp.text
        method_name = f"{method.upper()} {urlparse(full).path}"
        payloads = self.extractor.process_call(
            method_name,
            (),
            kwargs,
            data,
            client=self.session,
            is_streaming=False,
        )
        for payload in payloads:
            if "service_id" not in payload:
                payload["service_id"] = service_id
            self._augment_payload(payload)
        if payloads:
            self.tracked_payloads.extend(payloads)
            for p in payloads:
                self.delivery.deliver({"usage_records": [p]})
        return resp

    # attribute proxying ------------------------------------------
    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.session, name)
        if name.lower() in _HTTP_METHODS and callable(attr):

            async def wrapper(*args, **kwargs):
                method = name if name != "request" else args[0]
                url = args[1] if name == "request" else args[0]
                return await self.request(method, url, **kwargs)

            return wrapper
        return attr

    def get_tracked_payloads(self) -> List[dict[str, Any]]:
        return list(self.tracked_payloads)

    # delivery helpers -------------------------------------------
    def start_delivery(self) -> None:
        self.delivery.start()

    async def stop_delivery(self) -> None:
        await self.delivery.stop()

    async def __aenter__(self) -> "AsyncRestUsageWrapper":
        self.start_delivery()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop_delivery()

__all__ = ["RestUsageWrapper", "AsyncRestUsageWrapper"]

