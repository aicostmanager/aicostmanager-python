from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from .common import Granularity


class UsageEvent(BaseModel):
    event_id: str
    config_id: str
    service_id: Optional[str] = None
    timestamp: str
    response_id: str
    client_customer_key: Optional[str] = None
    usage: Dict[str, Any] = Field(default_factory=dict)
    base_url: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class UsageRollup(BaseModel):
    client_customer_key: Optional[str] = None
    service_id: str
    date: str
    quantity: float
    cost: float

    model_config = ConfigDict(from_attributes=True)


class UsageEventFilters(BaseModel):
    """Query parameters for ``list_usage_events``/``iter_usage_events``."""

    client_customer_key: Optional[str] = None
    config_id: Optional[str] = None
    service_id: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

    model_config = ConfigDict(extra="forbid")


class RollupFilters(BaseModel):
    """Query parameters for ``list_usage_rollups``/``iter_usage_rollups``."""

    client_customer_key: Optional[str] = None
    service_id: Optional[str] = None
    granularity: Granularity = Granularity.DAILY
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

    model_config = ConfigDict(extra="forbid")
