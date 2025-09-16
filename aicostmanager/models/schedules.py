from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class ExportScheduleOut(BaseModel):
    """Schema for export schedule response"""

    name: str
    description: Optional[str] = ""
    data_type: str = "api_cost_events"
    filters: Dict[str, Any]
    format: str = "jsonl"
    compression: str = "gzip"
    frequency: str = "daily"
    expand_context: bool = False
    destination_webhook_uuid: str
    uuid: str
    team_uuid: str
    active: bool
    next_run: Optional[str] = None  # datetime string
    last_run: Optional[str] = None  # datetime string
    created_at: str  # datetime string
    updated_at: str  # datetime string

    model_config = ConfigDict(from_attributes=True)


class ExportScheduleCreate(BaseModel):
    """Schema for creating export schedule"""

    name: str
    description: Optional[str] = ""
    data_type: str = "api_cost_events"
    filters: Dict[str, Any]
    format: str = "jsonl"
    compression: str = "gzip"
    frequency: str = "daily"
    expand_context: bool = False
    destination_webhook_id: str

    model_config = ConfigDict(extra="forbid")


class ExportSchedulesResponse(BaseModel):
    """Response schema for list of export schedules"""

    schedules: List[ExportScheduleOut]
    total_count: int
    active_count: int

    model_config = ConfigDict(from_attributes=True)


class ExportScheduleUpdate(BaseModel):
    """Schema for updating export schedule"""

    name: Optional[str] = None
    description: Optional[str] = None
    data_type: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    format: Optional[str] = None
    compression: Optional[str] = None
    frequency: Optional[str] = None
    destination_webhook_uuid: Optional[str] = None
    expand_context: Optional[bool] = None
    active: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")


class ExportJobOut(BaseModel):
    """Schema for export job response"""

    uuid: str
    schedule_uuid: str
    team_uuid: str
    window_start: str  # datetime string
    window_end: str  # datetime string
    status: str
    row_count: Optional[int] = None
    byte_size: Optional[int] = None
    file_hash: Optional[str] = None
    storage_url: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: str  # datetime string
    started_at: Optional[str] = None  # datetime string
    completed_at: Optional[str] = None  # datetime string
    webhook_sent_at: Optional[str] = None  # datetime string

    model_config = ConfigDict(from_attributes=True)


class ExportJobsResponse(BaseModel):
    """Response schema for list of export jobs"""

    jobs: List[ExportJobOut]
    total_count: int

    model_config = ConfigDict(from_attributes=True)


class ExportJobTriggerResponse(BaseModel):
    """Response schema for manually triggering export job"""

    job_uuid: str
    message: str

    model_config = ConfigDict(from_attributes=True)
