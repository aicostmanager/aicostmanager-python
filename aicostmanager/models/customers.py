from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class CustomerIn(BaseModel):
    customer_key: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class CustomerOut(CustomerIn):
    uuid: str

    model_config = ConfigDict(from_attributes=True)


class CustomerFilters(BaseModel):
    """Query parameters for ``list_customers``."""

    customer_key: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

    model_config = ConfigDict(extra="forbid")
