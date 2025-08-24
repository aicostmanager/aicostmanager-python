from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .common import PaginatedResponse


class CostEvent(BaseModel):
    """Simplified cost event representation."""

    vendor_id: str
    service_id: str
    cost_unit_id: str
    quantity: Decimal
    cost_per_unit: Decimal
    cost: Decimal

    model_config = ConfigDict(from_attributes=True)


class CostEventFilters(BaseModel):
    """Query parameters for ``list_costs``/``iter_costs``."""

    response_id: Optional[str] = None
    api_key_id: Optional[List[UUID]] = None
    client_customer_key: Optional[List[str]] = None
    service_key: Optional[List[str]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

    model_config = ConfigDict(extra="allow")


class CostEventsResponse(PaginatedResponse[CostEvent]):
    results: List[CostEvent] = []
