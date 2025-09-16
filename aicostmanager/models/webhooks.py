from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class WebhookEndpointOut(BaseModel):
    """Schema for webhook endpoint response"""

    url: str
    secret: str
    active: bool = True
    tolerance: int = 300
    uuid: str
    team_uuid: str
    created_at: str  # datetime string
    updated_at: str  # datetime string

    model_config = ConfigDict(from_attributes=True)


class WebhookEndpointCreate(BaseModel):
    """Schema for creating webhook endpoint"""

    url: str
    secret: str
    active: bool = True
    tolerance: int = 300

    model_config = ConfigDict(extra="forbid")


class WebhookEndpointsResponse(BaseModel):
    """Response schema for list of webhook endpoints"""

    endpoints: List[WebhookEndpointOut]
    total_count: int
    active_count: int

    model_config = ConfigDict(from_attributes=True)


class WebhookEndpointUpdate(BaseModel):
    """Schema for updating webhook endpoint"""

    url: Optional[str] = None
    secret: Optional[str] = None
    active: Optional[bool] = None
    tolerance: Optional[int] = None

    model_config = ConfigDict(extra="forbid")
