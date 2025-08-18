from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class ServiceConfigItem(BaseModel):
    config_id: str
    api_id: str
    version: str
    public_key: str
    key_id: str
    encrypted_payload: str


class ServiceConfigListResponse(BaseModel):
    service_configs: List[ServiceConfigItem] = Field(default_factory=list)
    triggered_limits: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
