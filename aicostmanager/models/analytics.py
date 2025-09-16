from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class DateFilterSchema(BaseModel):
    start_date: Optional[str] = None  # date string
    end_date: Optional[str] = None  # date string
    client_customer_key: Optional[str] = None


class SnapshotFilterSchema(BaseModel):
    service_key: Optional[str] = None
    client_customer_key: Optional[str] = None


class SnapshotTotalsSchema(BaseModel):
    cost: float
    count: int


class SnapshotsResponseSchema(BaseModel):
    snapshot_24h: SnapshotTotalsSchema
    snapshot_7d: SnapshotTotalsSchema
    snapshot_mtd: SnapshotTotalsSchema
    snapshot_ytd: SnapshotTotalsSchema


class TrendsFilterSchema(BaseModel):
    period: str = "7d"
    service_key: Optional[str] = None
    client_customer_key: Optional[str] = None


class TrendPointSchema(BaseModel):
    label: str
    cost: float
    count: int


class TrendsResponseSchema(BaseModel):
    period: str
    data: List[TrendPointSchema]


class CustomerBreakdownFilterSchema(BaseModel):
    start_date: Optional[str] = None  # date string
    end_date: Optional[str] = None  # date string
    service_key: Optional[str] = None
    provider_id: Optional[str] = None


class CustomerBreakdownSchema(BaseModel):
    client_customer_key: str
    total_cost: float
    event_count: int


class CustomerTokenBreakdownSchema(BaseModel):
    client_customer_key: str
    total_tokens: float
    event_count: int
