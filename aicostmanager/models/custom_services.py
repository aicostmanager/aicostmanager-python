from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CustomCostUnitIn(BaseModel):
    """Schema for creating/updating a custom cost unit"""

    name: str = Field(max_length=100)
    cost: Any  # number or string
    unit: str = Field(max_length=20)
    per_quantity: int = 1
    min_units: int = 0
    max_units: int = 10000000
    currency: str = "USD"  # ISO currency code
    is_active: bool = True

    model_config = ConfigDict(extra="forbid")


class CustomCostUnitOut(BaseModel):
    """Schema for custom cost unit output"""

    name: str
    cost: Any  # number or string
    unit: str
    per_quantity: int
    min_units: int
    max_units: int
    currency: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CustomServiceIn(BaseModel):
    """Schema for creating/updating a custom service"""

    custom_service_key: str = Field(max_length=100, min_length=1)
    configuration: Optional[Dict[str, Any]] = None
    is_active: bool = True
    cost_units: Optional[List[CustomCostUnitIn]] = None

    model_config = ConfigDict(extra="forbid")


class CustomServiceSummaryOut(BaseModel):
    """Schema for custom service summary (used in lists)"""

    uuid: str
    custom_service_key: str
    is_active: bool
    is_deleted: bool
    created_at: str  # datetime string
    updated_at: str  # datetime string
    cost_units_count: int

    model_config = ConfigDict(from_attributes=True)


class CustomServiceOut(BaseModel):
    """Schema for custom service output"""

    uuid: str
    custom_service_key: str
    configuration: Optional[Dict[str, Any]] = None
    is_active: bool
    is_deleted: bool
    created_at: str  # datetime string
    updated_at: str  # datetime string
    cost_units: List[CustomCostUnitOut]
    team_uuid: str
    team_name: str

    model_config = ConfigDict(from_attributes=True)


class CustomServiceFilter(BaseModel):
    """Schema for filtering custom services"""

    is_active: Optional[bool] = None
    is_deleted: Optional[bool] = None
    has_cost_units: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")
