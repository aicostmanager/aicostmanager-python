from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Iterable, Optional

import httpx

from ..models import (
    ApiCostEventOut,
    CostEventFilters,
    CostEventsResponse,
    CostUnitOut,
    CustomerBreakdownFilterSchema,
    CustomerBreakdownSchema,
    CustomerFilters,
    CustomerIn,
    CustomerOut,
    CustomerTokenBreakdownSchema,
    CustomServiceFilter,
    CustomServiceIn,
    CustomServiceOut,
    CustomServiceSummaryOut,
    DateFilterSchema,
    ExportJobOut,
    ExportJobsResponse,
    ExportJobTriggerResponse,
    ExportScheduleCreate,
    ExportScheduleOut,
    ExportSchedulesResponse,
    ExportScheduleUpdate,
    GeneratedReportOut,
    LimitEventOut,
    PaginatedResponse,
    RollupFilters,
    ServiceOut,
    SnapshotFilterSchema,
    SnapshotsResponseSchema,
    TrendsFilterSchema,
    TrendsResponseSchema,
    UsageEvent,
    UsageEventFilters,
    UsageLimitIn,
    UsageLimitOut,
    UsageLimitProgressOut,
    UsageRollup,
    VendorOut,
    WebhookEndpointCreate,
    WebhookEndpointOut,
    WebhookEndpointsResponse,
    WebhookEndpointUpdate,
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

    async def list_limit_events(
        self, limit_id: Optional[str] = None, **params: Any
    ) -> Iterable[LimitEventOut]:
        """List limit events."""
        params = {k: v for k, v in params.items() if v is not None}
        if limit_id is not None:
            params["limit_id"] = limit_id
        data = await self._request("GET", "/limit-events/", params=params)
        return [LimitEventOut.model_validate(i) for i in data]

    # Analytics methods
    async def analytics_costs_daily(
        self,
        filters: DateFilterSchema | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return await self._request("GET", "/analytics/costs/daily", params=params)

    async def analytics_costs_monthly(
        self,
        filters: DateFilterSchema | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return await self._request("GET", "/analytics/costs/monthly", params=params)

    async def analytics_costs_snapshots(
        self,
        filters: SnapshotFilterSchema | Dict[str, Any] | None = None,
        **params: Any,
    ) -> SnapshotsResponseSchema:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        data = await self._request("GET", "/analytics/costs/snapshots", params=params)
        return SnapshotsResponseSchema.model_validate(data)

    async def analytics_costs_trends(
        self,
        filters: TrendsFilterSchema | Dict[str, Any] | None = None,
        **params: Any,
    ) -> TrendsResponseSchema:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        data = await self._request("GET", "/analytics/costs/trends", params=params)
        return TrendsResponseSchema.model_validate(data)

    async def analytics_costs_peak_usage(
        self,
        filters: DateFilterSchema | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return await self._request("GET", "/analytics/costs/peak-usage", params=params)

    async def analytics_customers_costs(
        self,
        filters: CustomerBreakdownFilterSchema | Dict[str, Any] | None = None,
        **params: Any,
    ) -> List[CustomerBreakdownSchema]:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        data = await self._request("GET", "/analytics/customers/costs", params=params)
        return [CustomerBreakdownSchema.model_validate(i) for i in data]

    async def analytics_services_ranking(
        self,
        filters: DateFilterSchema | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return await self._request("GET", "/analytics/services/ranking", params=params)

    async def analytics_vendors_comparison(
        self,
        filters: DateFilterSchema | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return await self._request(
            "GET", "/analytics/vendors/comparison", params=params
        )

    async def analytics_services_efficiency(
        self,
        filters: DateFilterSchema | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return await self._request(
            "GET", "/analytics/services/efficiency", params=params
        )

    async def analytics_services_usage(
        self,
        filters: DateFilterSchema | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return await self._request("GET", "/analytics/services/usage", params=params)

    async def analytics_vendors_usage(
        self,
        filters: DateFilterSchema | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return await self._request("GET", "/analytics/vendors/usage", params=params)

    async def analytics_customers_tokens(
        self,
        filters: CustomerBreakdownFilterSchema | Dict[str, Any] | None = None,
        **params: Any,
    ) -> List[CustomerTokenBreakdownSchema]:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        data = await self._request("GET", "/analytics/customers/tokens", params=params)
        return [CustomerTokenBreakdownSchema.model_validate(i) for i in data]

    # Reports methods
    async def list_reports(
        self, **params: Any
    ) -> PaginatedResponse[GeneratedReportOut]:
        data = await self._request("GET", "/reports/", params=params)
        return PaginatedResponse[GeneratedReportOut].model_validate(data)

    async def get_report(self, report_id: str) -> GeneratedReportOut:
        data = await self._request("GET", f"/reports/{report_id}/")
        return GeneratedReportOut.model_validate(data)

    async def download_report(self, report_id: str) -> Any:
        """Download generated report file."""
        return await self._request("GET", f"/reports/{report_id}/download/")

    # Cost events methods
    async def list_cost_events(
        self,
        filters: CostEventFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> CostEventsResponse:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        data = await self._request("GET", "/costs/", params=params)
        return CostEventsResponse.model_validate(data)

    async def list_cost_events_by_response_id(
        self, response_id: str
    ) -> List[ApiCostEventOut]:
        data = await self._request("GET", f"/cost-events/{response_id}")
        return [ApiCostEventOut.model_validate(i) for i in data]

    # Webhook methods
    async def create_webhook_endpoint(
        self, data: WebhookEndpointCreate | Dict[str, Any]
    ) -> WebhookEndpointOut:
        payload = (
            data.model_dump(mode="json")
            if isinstance(data, WebhookEndpointCreate)
            else data
        )
        resp = await self._request("POST", "/webhooks/", json=payload)
        return WebhookEndpointOut.model_validate(resp)

    async def list_webhook_endpoints(
        self, active_only: bool = False, **params: Any
    ) -> WebhookEndpointsResponse:
        params = {k: v for k, v in params.items() if v is not None}
        params["active_only"] = active_only
        data = await self._request("GET", "/webhooks/", params=params)
        return WebhookEndpointsResponse.model_validate(data)

    async def get_webhook_endpoint(self, webhook_uuid: str) -> WebhookEndpointOut:
        data = await self._request("GET", f"/webhooks/{webhook_uuid}/")
        return WebhookEndpointOut.model_validate(data)

    async def update_webhook_endpoint(
        self, webhook_uuid: str, data: WebhookEndpointUpdate | Dict[str, Any]
    ) -> WebhookEndpointOut:
        payload = (
            data.model_dump(mode="json", exclude_none=True)
            if isinstance(data, WebhookEndpointUpdate)
            else data
        )
        resp = await self._request("PUT", f"/webhooks/{webhook_uuid}/", json=payload)
        return WebhookEndpointOut.model_validate(resp)

    async def delete_webhook_endpoint(self, webhook_uuid: str) -> None:
        await self._request("DELETE", f"/webhooks/{webhook_uuid}/")
        return None

    # Schedule methods
    async def create_export_schedule(
        self, data: ExportScheduleCreate | Dict[str, Any]
    ) -> ExportScheduleOut:
        payload = (
            data.model_dump(mode="json")
            if isinstance(data, ExportScheduleCreate)
            else data
        )
        resp = await self._request("POST", "/schedules/", json=payload)
        return ExportScheduleOut.model_validate(resp)

    async def list_export_schedules(
        self, active_only: bool = True, **params: Any
    ) -> ExportSchedulesResponse:
        params = {k: v for k, v in params.items() if v is not None}
        params["active_only"] = active_only
        data = await self._request("GET", "/schedules/", params=params)
        return ExportSchedulesResponse.model_validate(data)

    async def get_export_schedule(self, schedule_uuid: str) -> ExportScheduleOut:
        data = await self._request("GET", f"/schedules/{schedule_uuid}/")
        return ExportScheduleOut.model_validate(data)

    async def update_export_schedule(
        self, schedule_uuid: str, data: ExportScheduleUpdate | Dict[str, Any]
    ) -> ExportScheduleOut:
        payload = (
            data.model_dump(mode="json", exclude_none=True)
            if isinstance(data, ExportScheduleUpdate)
            else data
        )
        resp = await self._request("PUT", f"/schedules/{schedule_uuid}/", json=payload)
        return ExportScheduleOut.model_validate(resp)

    async def delete_export_schedule(self, schedule_uuid: str) -> None:
        await self._request("DELETE", f"/schedules/{schedule_uuid}/")
        return None

    async def list_export_jobs(self, **params: Any) -> ExportJobsResponse:
        data = await self._request("GET", "/jobs/", params=params)
        return ExportJobsResponse.model_validate(data)

    async def get_export_job(self, job_uuid: str) -> ExportJobOut:
        data = await self._request("GET", f"/jobs/{job_uuid}/")
        return ExportJobOut.model_validate(data)

    async def trigger_export_job(self, schedule_uuid: str) -> ExportJobTriggerResponse:
        data = await self._request("POST", f"/schedules/{schedule_uuid}/run/")
        return ExportJobTriggerResponse.model_validate(data)

    # Custom services methods
    async def list_custom_services(
        self,
        filters: CustomServiceFilter | Dict[str, Any] | None = None,
        **params: Any,
    ) -> List[CustomServiceSummaryOut]:
        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        data = await self._request("GET", "/custom-services/", params=params)
        return [CustomServiceSummaryOut.model_validate(i) for i in data]

    async def create_custom_service(
        self, data: CustomServiceIn | Dict[str, Any]
    ) -> CustomServiceOut:
        payload = (
            data.model_dump(mode="json") if isinstance(data, CustomServiceIn) else data
        )
        resp = await self._request("POST", "/custom-services/", json=payload)
        return CustomServiceOut.model_validate(resp)

    async def get_custom_service(self, uuid: str) -> CustomServiceOut:
        data = await self._request("GET", f"/custom-services/{uuid}/")
        return CustomServiceOut.model_validate(data)

    async def update_custom_service(
        self, uuid: str, data: CustomServiceIn | Dict[str, Any]
    ) -> CustomServiceOut:
        payload = (
            data.model_dump(mode="json") if isinstance(data, CustomServiceIn) else data
        )
        resp = await self._request("PUT", f"/custom-services/{uuid}/", json=payload)
        return CustomServiceOut.model_validate(resp)

    async def delete_custom_service(self, uuid: str) -> None:
        await self._request("DELETE", f"/custom-services/{uuid}/")
        return None

    async def get_openapi_schema(self) -> Any:
        return await self._request("GET", "/openapi.json")
