from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

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


class RoundingConfig(BaseModel):
    """Schema for rounding configuration in mappings"""

    mode: str = Field(description="Rounding mode: 'ceil', 'floor', 'round'")
    increment: Optional[float] = Field(default=None, description="Increment to round to")

    model_config = ConfigDict(extra="forbid")


class Condition(BaseModel):
    """Schema for conditional logic in mappings"""

    equals: Optional[Dict[str, Any]] = Field(default=None, description="Equals condition")
    regex: Optional[Dict[str, Any]] = Field(default=None, description="Regex condition")

    model_config = ConfigDict(extra="forbid")


class CostUnitSwitch(BaseModel):
    """Schema for cost unit switching based on field values"""

    field: str = Field(description="Field to check for switching")
    cases: Dict[str, str] = Field(description="Mapping of field values to cost unit names")
    default: str = Field(description="Default cost unit name")

    model_config = ConfigDict(extra="forbid")


class Mapping(BaseModel):
    """Schema for field-to-cost-unit mappings"""

    cost_unit: Optional[str] = Field(default=None, description="Name of cost unit to assign to")
    cost_unit_switch: Optional[CostUnitSwitch] = Field(default=None, description="Conditional cost unit switching")
    field: str = Field(description="Path to quantity field in usage payload")
    divide_by: Optional[float] = Field(default=None, description="Divide quantity by this value")
    multiply_by: Optional[float] = Field(default=None, description="Multiply quantity by this value")
    min_value: Optional[float] = Field(default=None, description="Minimum value to use")
    max_value: Optional[float] = Field(default=None, description="Maximum value to use")
    rounding: Optional[RoundingConfig] = Field(default=None, description="Rounding configuration")
    only_if: Optional[Condition] = Field(default=None, description="Only apply if condition matches")

    model_config = ConfigDict(extra="forbid")


class MappingGroup(BaseModel):
    """Schema for conditional mapping groups"""

    when: Condition = Field(description="Condition that must be met")
    mappings: List[Mapping] = Field(description="Mappings to apply when condition is met")

    model_config = ConfigDict(extra="forbid")


class CustomServiceConfiguration(BaseModel):
    """Schema for custom service configuration"""

    cost_units: List[CustomCostUnitIn] = Field(description="Cost units for this service")
    mappings: Optional[List[Mapping]] = Field(default=None, description="Field-to-cost-unit mappings")
    mapping_groups: Optional[List[MappingGroup]] = Field(default=None, description="Conditional mapping groups")
    exclusions: Optional[List[Condition]] = Field(default=None, description="Conditions to exclude events")

    model_config = ConfigDict(extra="forbid")


class CustomServiceIn(BaseModel):
    """Schema for creating/updating a custom service"""

    custom_service_key: str = Field(max_length=100, min_length=1)
    configuration: CustomServiceConfiguration
    is_active: bool = True

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
    configuration: CustomServiceConfiguration
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
