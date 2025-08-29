from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Iterable, Optional

import httpx

from ..models import (
    CostUnitOut,
    CustomerFilters,
    CustomerIn,
    CustomerOut,
    PaginatedResponse,
    RollupFilters,
    ServiceOut,
    UsageEvent,
    UsageEventFilters,
    UsageLimitIn,
    UsageLimitOut,
    UsageLimitProgressOut,
    UsageRollup,
    VendorOut,
)
from .base import BaseClient
from .exceptions import APIRequestError


class AsyncCostManagerClient(BaseClient):
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
        super().__init__(
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
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

    async def get_triggered_limits(self) -> Dict[str, Any]:
        """Asynchronously fetch triggered limit information."""
        return await self._request("GET", "/triggered-limits")

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

    async def list_usage_limit_progress(self) -> Iterable[UsageLimitProgressOut]:
        data = await self._request("GET", "/usage-limits/progress/")
        return [UsageLimitProgressOut.model_validate(i) for i in data]

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
