from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

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
    """Schema for error responses"""

    detail: str
    code: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[T] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TrackResult(BaseModel):
    """Per-record result for /track"""

    response_id: str
    cost_events: Optional[List[Dict[str, Any]]] = None
    errors: Optional[List[str]] = None


class TriggeredLimitPayload(BaseModel):
    """Encrypted triggered limits payload"""

    version: str
    public_key: str
    key_id: str
    encrypted_payload: str


class TrackResponse(BaseModel):
    """Response from /track endpoint"""

    results: List[TrackResult]
    triggered_limits: Optional[TriggeredLimitPayload] = None


class TrackedRecord(BaseModel):
    """Individual record for /track"""

    service_key: Optional[str] = None
    response_id: Optional[str] = None
    timestamp: Optional[str] = None  # ISO 8601 string or UNIX epoch seconds
    customer_key: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    payload: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="forbid")


class TrackRequest(BaseModel):
    """Request body for /track endpoint"""

    tracked: List[TrackedRecord] = Field(min_length=1)
    skip_limits: bool = False

    model_config = ConfigDict(extra="forbid")
