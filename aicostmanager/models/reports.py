from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class GeneratedReportOut(BaseModel):
    report_id: str
    status: str
    created: str  # datetime string
    last_updated: str  # datetime string
    expires_at: str  # datetime string
    parameters: Dict[str, Any]
    download_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
