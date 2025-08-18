from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional, Generic, TypeVar

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


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[T] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
