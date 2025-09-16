from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict

from .common import Period, ThresholdType


class UsageLimitIn(BaseModel):
    threshold_type: ThresholdType
    amount: Any  # number or string
    period: Period
    service_key: Optional[str] = None
    client: Optional[str] = None
    team_uuid: Optional[str] = None
    user_uuid: Optional[str] = None
    user_email: Optional[str] = None
    api_key_uuid: Optional[str] = None
    notification_list: Optional[List[str]] = None
    active: Optional[bool] = True

    model_config = ConfigDict(extra="forbid")


class UsageLimitOut(BaseModel):
    uuid: str
    threshold_type: ThresholdType
    amount: Any  # number or string
    period: Period
    service: Optional[str] = None
    client: Optional[str] = None
    notification_list: Optional[List[str]] = None
    active: bool

    model_config = ConfigDict(from_attributes=True)


class UsageLimitProgressOut(UsageLimitOut):
    current_spend: Any  # number or string
    remaining_amount: Any  # number or string


class LimitEventOut(BaseModel):
    uuid: str
    limit_id: str
    triggered_at: str  # datetime string
    sent_at: Optional[str] = None  # datetime string
    expires_at: Optional[str] = None  # datetime string

    model_config = ConfigDict(from_attributes=True)
