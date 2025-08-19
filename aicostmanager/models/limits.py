from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from .common import Period, ThresholdType


class UsageLimitIn(BaseModel):
    threshold_type: ThresholdType
    amount: Decimal
    period: Period
    vendor: Optional[str] = None
    service: Optional[str] = None
    client: Optional[str] = None
    team_uuid: Optional[str] = None
    user_uuid: Optional[str] = None
    api_key_uuid: Optional[str] = None
    notification_list: Optional[List[str]] = None
    active: Optional[bool] = True

    model_config = ConfigDict(extra="forbid")


class UsageLimitOut(BaseModel):
    uuid: str
    threshold_type: ThresholdType
    amount: Decimal
    period: Period
    vendor: Optional[str] = None
    service: Optional[str] = None
    client: Optional[str] = None
    team_uuid: Optional[str] = None
    user_uuid: Optional[str] = None
    api_key_uuid: Optional[str] = None
    notification_list: Optional[List[str]] = None
    active: bool

    model_config = ConfigDict(from_attributes=True)


class UsageLimitProgressOut(UsageLimitOut):
    current_spend: Decimal
    remaining_amount: Decimal
