from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class CostEventItem(BaseModel):
    """Simplified cost event representation."""

    provider_id: str
    service_key: str
    cost_unit_id: str
    quantity: Any  # number or string
    cost_per_unit: Any  # number or string
    cost: Any  # number or string

    model_config = ConfigDict(from_attributes=True)


class CostEventFilters(BaseModel):
    """Query parameters for cost event listing."""

    response_id: Optional[str] = None
    api_key_id: Optional[List[str]] = None  # UUID strings
    client_customer_key: Optional[List[str]] = None
    service_key: Optional[List[str]] = None
    start_date: Optional[str] = None  # date string
    end_date: Optional[str] = None  # date string

    model_config = ConfigDict(extra="forbid")


class CostEventsResponse(BaseModel):
    """Paginated list of cost events."""

    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[CostEventItem]

    model_config = ConfigDict(from_attributes=True)


class ApiCostEventOut(BaseModel):
    """Schema representing a stored ApiCostEvent record."""

    uuid: str
    event_id: str
    team_id: str
    api_key_id: str
    timestamp: str  # datetime string
    client_customer_key: Optional[str] = None
    response_id: str
    provider_id: str
    service_key: str
    cost_unit_id: str
    quantity: Any  # number or string
    cost_per_unit: Any  # number or string
    cost: Any  # number or string
    context: Optional[Dict[str, Any]] = None
    hourly_rollup_status: str
    daily_rollup_status: str

    model_config = ConfigDict(from_attributes=True)
