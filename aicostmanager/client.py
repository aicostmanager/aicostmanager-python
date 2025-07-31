"""Client for interacting with the AICostManager API."""

from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterable, Iterator, Optional

import httpx
import requests

from .models import (
    ApiUsageRequest,
    ApiUsageResponse,
    CostUnitOut,
    CustomerFilters,
    CustomerIn,
    CustomerOut,
    ErrorResponse,
    PaginatedResponse,
    RollupFilters,
    ServiceConfigListResponse,
    ServiceOut,
    UsageEvent,
    UsageEventFilters,
    UsageLimitIn,
    UsageLimitOut,
    UsageRollup,
    VendorOut,
)


class AICMError(Exception):
    """Base exception for SDK errors."""


class MissingConfiguration(AICMError):
    """Raised when required configuration is missing."""


class APIRequestError(AICMError):
    """Raised for non-successful HTTP responses."""

    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.error_response: ErrorResponse | None = None
        self.error: str | None = None
        self.message: str | None = None
        self.details: Any | None = None
        if isinstance(detail, dict):
            try:
                self.error_response = ErrorResponse.model_validate(detail)
                self.error = self.error_response.error
                self.message = self.error_response.message
                self.details = self.error_response.details
            except Exception:
                self.error = detail.get("error")
                self.message = detail.get("message")
        super().__init__(f"API request failed with status {status_code}: {detail}")


class UsageLimitExceeded(AICMError):
    """Raised when a usage limit has been exceeded and blocks API calls."""

    def __init__(self, triggered_limits: list) -> None:
        self.triggered_limits = triggered_limits
        limit_info = ", ".join(
            [f"limit {tl.limit_id} ({tl.threshold_type})" for tl in triggered_limits]
        )
        super().__init__(f"Usage limit exceeded: {limit_info}")


class CostManagerClient:
    """Client for AICostManager endpoints."""

    def __init__(
        self,
        *,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        aicm_ini_path: Optional[str] = None,
        session: Optional[requests.Session] = None,
        proxies: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.api_key = aicm_api_key or os.getenv("AICM_API_KEY")
        self.api_base = aicm_api_base or os.getenv(
            "AICM_API_BASE", "https://aicostmanager.com"
        )
        self.api_url = aicm_api_url or os.getenv("AICM_API_URL", "/api/v1")
        self.ini_path = (
            aicm_ini_path
            or os.getenv("AICM_INI_PATH")
            or str(Path.home() / ".config" / "aicostmanager" / "AICM.INI")
        )
        if not self.api_key:
            raise MissingConfiguration(
                "API key not provided. Set AICM_API_KEY environment variable or pass aicm_api_key"
            )
        if session is None:
            session = requests.Session()
            if proxies:
                setattr(session, "proxies", getattr(session, "proxies", {}))
                session.proxies.update(proxies)
        elif proxies:
            setattr(session, "proxies", getattr(session, "proxies", {}))
            session.proxies.update(proxies)
        self.session = session
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "aicostmanager-python",
            }
        )
        if headers:
            self.session.headers.update(headers)
        self._configs_etag: str | None = None

    @property
    def configs_etag(self) -> str | None:
        """Return the last ETag seen from ``/configs``."""
        return self._configs_etag

    @property
    def api_root(self) -> str:
        """Return the combined AICostManager API base URL."""
        return self.api_base.rstrip("/") + self.api_url

    def close(self) -> None:
        """Close the underlying requests session."""
        self.session.close()

    def __enter__(self) -> "CostManagerClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # internal helper
    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = path if path.startswith("http") else self.api_root + path
        resp = self.session.request(method, url, **kwargs)
        if not resp.ok:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise APIRequestError(resp.status_code, detail)
        if resp.status_code == 204:
            return None
        return resp.json()

    def _iter_paginated(self, path: str, **params: Any) -> Iterator[dict]:
        while True:
            data = self._request("GET", path, params=params)
            for item in data.get("results", []):
                yield item
            next_url = data.get("next")
            if not next_url:
                break
            if next_url.startswith(self.api_root):
                path = next_url[len(self.api_root) :]
            else:
                path = next_url
            params = {}

    # endpoint methods
    def get_configs(
        self, *, etag: str | None = None
    ) -> ServiceConfigListResponse | None:
        """Fetch configuration data with optional caching.

        If ``etag`` is provided it will be sent using ``If-None-Match`` and the
        method returns ``None`` when the server responds with ``304 Not
        Modified``.
        """

        headers: dict[str, str] | None = None
        if etag:
            headers = {"If-None-Match": etag}
        resp = self.session.request("GET", self.api_root + "/configs", headers=headers)
        if resp.status_code == 304:
            self._configs_etag = etag
            return None
        if not resp.ok:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise APIRequestError(resp.status_code, detail)
        self._configs_etag = resp.headers.get("ETag")
        data = resp.json()
        return ServiceConfigListResponse.model_validate(data)

    def track_usage(self, data: ApiUsageRequest | Dict[str, Any]) -> ApiUsageResponse:
        payload = (
            data.model_dump(mode="json") if isinstance(data, ApiUsageRequest) else data
        )
        resp = self._request("POST", "/track-usage", json=payload)
        result = ApiUsageResponse.model_validate(resp)
        # Always update triggered_limits, even if empty - server may have cleared previous limits
        cp = configparser.ConfigParser()
        cp.read(self.ini_path)
        os.makedirs(os.path.dirname(self.ini_path), exist_ok=True)
        if "triggered_limits" not in cp:
            cp["triggered_limits"] = {}
        cp["triggered_limits"]["payload"] = json.dumps(result.triggered_limits or {})
        with open(self.ini_path, "w") as f:
            cp.write(f)
        return result

    def list_usage_events(
        self,
        filters: UsageEventFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return self._request("GET", "/usage/events/", params=params)

    def list_usage_events_typed(
        self,
        filters: UsageEventFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> PaginatedResponse[UsageEvent]:
        """Typed variant of :meth:`list_usage_events`."""
        data = self.list_usage_events(filters, **params)
        return PaginatedResponse[UsageEvent].model_validate(data)

    def iter_usage_events(
        self,
        filters: UsageEventFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Iterator[UsageEvent]:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        for item in self._iter_paginated("/usage/events/", **params):
            yield UsageEvent.model_validate(item)

    def get_usage_event(self, event_id: str) -> UsageEvent:
        data = self._request("GET", f"/usage/event/{event_id}/")
        return UsageEvent.model_validate(data)

    def list_usage_rollups(
        self,
        filters: RollupFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return self._request("GET", "/usage/rollups/", params=params)

    def list_usage_rollups_typed(
        self,
        filters: RollupFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> PaginatedResponse[UsageRollup]:
        """Typed variant of :meth:`list_usage_rollups`."""
        data = self.list_usage_rollups(filters, **params)
        return PaginatedResponse[UsageRollup].model_validate(data)

    def iter_usage_rollups(
        self,
        filters: RollupFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Iterator[UsageRollup]:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        for item in self._iter_paginated("/usage/rollups/", **params):
            yield UsageRollup.model_validate(item)

    def list_customers(
        self,
        filters: CustomerFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return self._request("GET", "/customers/", params=params)

    def list_customers_typed(
        self,
        filters: CustomerFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> PaginatedResponse[CustomerOut]:
        """Typed variant of :meth:`list_customers`."""
        data = self.list_customers(filters, **params)
        return PaginatedResponse[CustomerOut].model_validate(data)

    def iter_customers(self, **params: Any) -> Iterator[CustomerOut]:
        for item in self._iter_paginated("/customers/", **params):
            yield CustomerOut.model_validate(item)

    def create_customer(self, data: CustomerIn | Dict[str, Any]) -> CustomerOut:
        payload = data.model_dump(mode="json") if isinstance(data, CustomerIn) else data
        resp = self._request("POST", "/customers/", json=payload)
        return CustomerOut.model_validate(resp)

    def get_customer(self, customer_id: str) -> CustomerOut:
        data = self._request("GET", f"/customers/{customer_id}/")
        return CustomerOut.model_validate(data)

    def update_customer(
        self, customer_id: str, data: CustomerIn | Dict[str, Any]
    ) -> CustomerOut:
        payload = data.model_dump(mode="json") if isinstance(data, CustomerIn) else data
        resp = self._request("PUT", f"/customers/{customer_id}/", json=payload)
        return CustomerOut.model_validate(resp)

    def delete_customer(self, customer_id: str) -> None:
        self._request("DELETE", f"/customers/{customer_id}/")
        return None

    def list_usage_limits(self) -> Iterable[UsageLimitOut]:
        data = self._request("GET", "/usage-limits/")
        return [UsageLimitOut.model_validate(i) for i in data]

    def create_usage_limit(self, data: UsageLimitIn | Dict[str, Any]) -> UsageLimitOut:
        payload = (
            data.model_dump(mode="json") if isinstance(data, UsageLimitIn) else data
        )
        resp = self._request("POST", "/usage-limits/", json=payload)
        return UsageLimitOut.model_validate(resp)

    def get_usage_limit(self, limit_id: str) -> UsageLimitOut:
        data = self._request("GET", f"/usage-limits/{limit_id}/")
        return UsageLimitOut.model_validate(data)

    def update_usage_limit(
        self, limit_id: str, data: UsageLimitIn | Dict[str, Any]
    ) -> UsageLimitOut:
        payload = (
            data.model_dump(mode="json") if isinstance(data, UsageLimitIn) else data
        )
        resp = self._request("PUT", f"/usage-limits/{limit_id}/", json=payload)
        return UsageLimitOut.model_validate(resp)

    def delete_usage_limit(self, limit_id: str) -> None:
        self._request("DELETE", f"/usage-limits/{limit_id}/")
        return None

    def list_vendors(self) -> Iterable[VendorOut]:
        data = self._request("GET", "/vendors/")
        return [VendorOut.model_validate(i) for i in data]

    def list_vendor_services(self, vendor: str) -> Iterable[ServiceOut]:
        data = self._request("GET", "/services/", params={"vendor": vendor})
        # Add vendor field to each service object since the API doesn't include it
        for service in data:
            service["vendor"] = vendor
        return [ServiceOut.model_validate(i) for i in data]

    def list_service_costs(self, vendor: str, service: str) -> Iterable[CostUnitOut]:
        """List cost units for a service."""
        data = self._request(
            "GET",
            "/service-costs/",
            params={"vendor": vendor, "service": service},
        )
        return [CostUnitOut.model_validate(i) for i in data]

    def get_openapi_schema(self) -> Any:
        return self._request("GET", "/openapi.json")


class AsyncCostManagerClient:
    """Asynchronous variant of :class:`CostManagerClient`."""

    def __init__(
        self,
        *,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        aicm_ini_path: Optional[str] = None,
        session: Optional[httpx.AsyncClient] = None,
        proxies: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.api_key = aicm_api_key or os.getenv("AICM_API_KEY")
        self.api_base = aicm_api_base or os.getenv(
            "AICM_API_BASE", "https://aicostmanager.com"
        )
        self.api_url = aicm_api_url or os.getenv("AICM_API_URL", "/api/v1")
        self.ini_path = (
            aicm_ini_path
            or os.getenv("AICM_INI_PATH")
            or str(Path.home() / ".config" / "aicostmanager" / "AICM.INI")
        )
        if not self.api_key:
            raise MissingConfiguration(
                "API key not provided. Set AICM_API_KEY environment variable or pass aicm_api_key"
            )
        if session is None:
            proxy = None
            if proxies:
                proxy = next(iter(proxies.values()))
            session = httpx.AsyncClient(proxy=proxy)
        self.session = session
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "aicostmanager-python",
            }
        )
        if headers:
            self.session.headers.update(headers)
        self._configs_etag: str | None = None

    @property
    def configs_etag(self) -> str | None:
        """Return the last ETag seen from ``/configs``."""
        return self._configs_etag

    @property
    def api_root(self) -> str:
        return self.api_base.rstrip("/") + self.api_url

    async def close(self) -> None:
        await self.session.aclose()

    async def __aenter__(self) -> "AsyncCostManagerClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = path if path.startswith("http") else self.api_root + path
        resp = await self.session.request(method, url, **kwargs)
        if not resp.status_code or not (200 <= resp.status_code < 300):
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise APIRequestError(resp.status_code, detail)
        if resp.status_code == 204:
            return None
        return resp.json()

    async def _iter_paginated(self, path: str, **params: Any) -> AsyncIterator[dict]:
        while True:
            data = await self._request("GET", path, params=params)
            for item in data.get("results", []):
                yield item
            next_url = data.get("next")
            if not next_url:
                break
            if next_url.startswith(self.api_root):
                path = next_url[len(self.api_root) :]
            else:
                path = next_url
            params = {}

    async def get_configs(
        self, *, etag: str | None = None
    ) -> ServiceConfigListResponse | None:
        """Asynchronously fetch configuration data with optional caching."""

        headers: dict[str, str] | None = None
        if etag:
            headers = {"If-None-Match": etag}
        resp = await self.session.request(
            "GET", self.api_root + "/configs", headers=headers
        )
        if resp.status_code == 304:
            self._configs_etag = etag
            return None
        if not (200 <= resp.status_code < 300):
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise APIRequestError(resp.status_code, detail)
        self._configs_etag = resp.headers.get("ETag")
        data = resp.json()
        return ServiceConfigListResponse.model_validate(data)

    async def track_usage(
        self, data: ApiUsageRequest | Dict[str, Any]
    ) -> ApiUsageResponse:
        payload = (
            data.model_dump(mode="json") if isinstance(data, ApiUsageRequest) else data
        )
        resp = await self._request("POST", "/track-usage", json=payload)
        result = ApiUsageResponse.model_validate(resp)
        # Always update triggered_limits, even if empty - server may have cleared previous limits
        cp = configparser.ConfigParser()
        cp.read(self.ini_path)
        os.makedirs(os.path.dirname(self.ini_path), exist_ok=True)
        if "triggered_limits" not in cp:
            cp["triggered_limits"] = {}
        cp["triggered_limits"]["payload"] = json.dumps(result.triggered_limits or {})
        with open(self.ini_path, "w") as f:
            cp.write(f)
        return result

    async def list_usage_events(
        self,
        filters: UsageEventFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return await self._request("GET", "/usage/events/", params=params)

    async def list_usage_events_typed(
        self,
        filters: UsageEventFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> PaginatedResponse[UsageEvent]:
        """Typed variant of :meth:`list_usage_events`."""
        data = await self.list_usage_events(filters, **params)
        return PaginatedResponse[UsageEvent].model_validate(data)

    async def iter_usage_events(
        self,
        filters: UsageEventFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> AsyncIterator[UsageEvent]:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        async for item in self._iter_paginated("/usage/events/", **params):
            yield UsageEvent.model_validate(item)

    async def get_usage_event(self, event_id: str) -> UsageEvent:
        data = await self._request("GET", f"/usage/event/{event_id}/")
        return UsageEvent.model_validate(data)

    async def list_usage_rollups(
        self,
        filters: RollupFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return await self._request("GET", "/usage/rollups/", params=params)

    async def list_usage_rollups_typed(
        self,
        filters: RollupFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> PaginatedResponse[UsageRollup]:
        """Typed variant of :meth:`list_usage_rollups`."""
        data = await self.list_usage_rollups(filters, **params)
        return PaginatedResponse[UsageRollup].model_validate(data)

    async def iter_usage_rollups(
        self,
        filters: RollupFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> AsyncIterator[UsageRollup]:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        async for item in self._iter_paginated("/usage/rollups/", **params):
            yield UsageRollup.model_validate(item)

    async def list_customers(
        self,
        filters: CustomerFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return await self._request("GET", "/customers/", params=params)

    async def list_customers_typed(
        self,
        filters: CustomerFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> PaginatedResponse[CustomerOut]:
        """Typed variant of :meth:`list_customers`."""
        data = await self.list_customers(filters, **params)
        return PaginatedResponse[CustomerOut].model_validate(data)

    async def iter_customers(self, **params: Any) -> AsyncIterator[CustomerOut]:
        async for item in self._iter_paginated("/customers/", **params):
            yield CustomerOut.model_validate(item)

    async def create_customer(self, data: CustomerIn | Dict[str, Any]) -> CustomerOut:
        payload = data.model_dump(mode="json") if isinstance(data, CustomerIn) else data
        resp = await self._request("POST", "/customers/", json=payload)
        return CustomerOut.model_validate(resp)

    async def get_customer(self, customer_id: str) -> CustomerOut:
        data = await self._request("GET", f"/customers/{customer_id}/")
        return CustomerOut.model_validate(data)

    async def update_customer(
        self, customer_id: str, data: CustomerIn | Dict[str, Any]
    ) -> CustomerOut:
        payload = data.model_dump(mode="json") if isinstance(data, CustomerIn) else data
        resp = await self._request("PUT", f"/customers/{customer_id}/", json=payload)
        return CustomerOut.model_validate(resp)

    async def delete_customer(self, customer_id: str) -> None:
        await self._request("DELETE", f"/customers/{customer_id}/")
        return None

    async def list_usage_limits(self) -> Iterable[UsageLimitOut]:
        data = await self._request("GET", "/usage-limits/")
        return [UsageLimitOut.model_validate(i) for i in data]

    async def create_usage_limit(
        self, data: UsageLimitIn | Dict[str, Any]
    ) -> UsageLimitOut:
        payload = (
            data.model_dump(mode="json") if isinstance(data, UsageLimitIn) else data
        )
        resp = await self._request("POST", "/usage-limits/", json=payload)
        return UsageLimitOut.model_validate(resp)

    async def get_usage_limit(self, limit_id: str) -> UsageLimitOut:
        data = await self._request("GET", f"/usage-limits/{limit_id}/")
        return UsageLimitOut.model_validate(data)

    async def update_usage_limit(
        self, limit_id: str, data: UsageLimitIn | Dict[str, Any]
    ) -> UsageLimitOut:
        payload = (
            data.model_dump(mode="json") if isinstance(data, UsageLimitIn) else data
        )
        resp = await self._request("PUT", f"/usage-limits/{limit_id}/", json=payload)
        return UsageLimitOut.model_validate(resp)

    async def delete_usage_limit(self, limit_id: str) -> None:
        await self._request("DELETE", f"/usage-limits/{limit_id}/")
        return None

    async def list_vendors(self) -> Iterable[VendorOut]:
        data = await self._request("GET", "/vendors/")
        return [VendorOut.model_validate(i) for i in data]

    async def list_vendor_services(self, vendor: str) -> Iterable[ServiceOut]:
        data = await self._request("GET", "/services/", params={"vendor": vendor})
        # Add vendor field to each service object since the API doesn't include it
        for service in data:
            service["vendor"] = vendor
        return [ServiceOut.model_validate(i) for i in data]

    async def list_service_costs(
        self, vendor: str, service: str
    ) -> Iterable[CostUnitOut]:
        """Asynchronously list cost units for a service."""
        data = await self._request(
            "GET",
            "/service-costs/",
            params={"vendor": vendor, "service": service},
        )
        return [CostUnitOut.model_validate(i) for i in data]

    async def get_openapi_schema(self) -> Any:
        return await self._request("GET", "/openapi.json")
