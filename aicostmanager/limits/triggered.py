from __future__ import annotations

from typing import List, Optional

from ..client import CostManagerClient
from ..config_manager import CostManagerConfig, TriggeredLimit
from .base import BaseLimitManager


class TriggeredLimitManager(BaseLimitManager):
    """Manage triggered limits fetched from the API and stored locally."""

    def __init__(
        self, client: CostManagerClient, config_manager: CostManagerConfig | None = None
    ) -> None:
        super().__init__(client)
        self.config_manager = config_manager or CostManagerConfig(client)

    def update_triggered_limits(self) -> None:
        data = self.client.get_triggered_limits() or {}
        if isinstance(data, dict):
            tl_data = data.get("triggered_limits", data)
        else:
            tl_data = data
        self.config_manager.write_triggered_limits(tl_data)

    def check_triggered_limits(
        self,
        api_key_id: str,
        service_key: Optional[str] = None,
        client_customer_key: Optional[str] = None,
    ) -> List[TriggeredLimit]:
        vendor = service_id = None
        if service_key and "::" in service_key:
            vendor, service_id = service_key.split("::", 1)
        elif service_key:
            service_id = service_key
        limits = self.config_manager.get_triggered_limits(
            service_id=service_id,
            service_vendor=vendor,
            client_customer_key=client_customer_key,
        )
        return [l for l in limits if l.api_key_id == api_key_id]
