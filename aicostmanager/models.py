from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Generic, TypeVar
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ThresholdType(str, Enum):
    ALERT = "alert"
    LIMIT = "limit"


class Period(str, Enum):
    DAY = "day"
    MONTH = "month"


class Granularity(str, Enum):
    """Aggregation window for usage rollups."""

    DAILY = "daily"
    HOURLY = "hourly"


class ValidationError(BaseModel):
    """Individual validation error from the API."""

    field: str
    message: str
    invalid_value: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str
    message: str
    details: Optional[List[ValidationError]] = None
    timestamp: Optional[str] = None


class ApiUsageRecord(BaseModel):
    """Individual usage record for /track-usage"""

    config_id: str
    service_id: str
    timestamp: str
    response_id: str
    usage: Dict[str, Any]
    base_url: Optional[str] = None
    client_customer_key: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="forbid")


class ApiUsageRequest(BaseModel):
    """Request body for /track-usage"""

    usage_records: List[ApiUsageRecord]

    model_config = ConfigDict(extra="forbid")


class ApiUsageResponse(BaseModel):
    event_ids: List[Dict[str, str]]
    triggered_limits: Dict[str, str]


class ServiceConfigItem(BaseModel):
    config_id: str
    api_id: str
    version: str
    public_key: str
    key_id: str
    encrypted_payload: str


class ServiceConfigListResponse(BaseModel):
    service_configs: List[ServiceConfigItem] = Field(default_factory=list)
    triggered_limits: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class CustomerIn(BaseModel):
    client_customer_key: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class CustomerOut(CustomerIn):
    uuid: str

    model_config = ConfigDict(from_attributes=True)


class UsageLimitIn(BaseModel):
    threshold_type: ThresholdType
    amount: Decimal
    period: Period
    vendor: Optional[str] = None
    service: Optional[str] = None
    client: Optional[str] = None
    notification_list: Optional[List[str]] = None
    active: Optional[bool] = True

    model_config = ConfigDict(extra="forbid")


class UsageLimitOut(BaseModel):
    uuid: str
    threshold_type: ThresholdType
    amount: Decimal
    period: Period
    vendor: Optional[str]
    service: Optional[str]
    client: Optional[str]
    notification_list: Optional[List[str]]
    active: bool

    model_config = ConfigDict(from_attributes=True)


class VendorOut(BaseModel):
    uuid: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class ServiceOut(BaseModel):
    uuid: str
    service_id: str
    vendor: str
    name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CostUnitOut(BaseModel):
    """Cost information for a service."""

    uuid: str
    name: str
    cost: Decimal
    unit: str
    per_quantity: int
    currency: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


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


class CustomerFilters(BaseModel):
    """Query parameters for ``list_customers``."""

    client_customer_key: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

    model_config = ConfigDict(extra="forbid")


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[T] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
