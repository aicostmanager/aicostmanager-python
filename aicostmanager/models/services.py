from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


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
