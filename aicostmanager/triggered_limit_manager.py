from __future__ import annotations

from typing import List, Optional

import jwt

from .client import CostManagerClient
from .ini_manager import IniManager


class TriggeredLimitManager:
    """Manage triggered limits fetched from the API and stored locally."""

    def __init__(self, client: CostManagerClient, ini_manager: IniManager | None = None) -> None:
        self.client = client
        self.ini_manager = ini_manager or IniManager(client.ini_path)

    def _decode(self, token: str, public_key: str) -> Optional[dict]:
        try:
            return jwt.decode(token, public_key, algorithms=["RS256"], issuer="aicm-api")
        except Exception:
            return None

    def update_triggered_limits(self) -> None:
        data = self.client.get_triggered_limits() or {}
        if isinstance(data, dict):
            tl_data = data.get("triggered_limits", data)
        else:
            tl_data = data
        self.ini_manager.write_triggered_limits(tl_data)

    def check_triggered_limits(
        self,
        api_key_id: str,
        service_key: Optional[str] = None,
        client_customer_key: Optional[str] = None,
    ) -> List[dict]:
        tl_raw = self.ini_manager.read_triggered_limits()
        token = tl_raw.get("encrypted_payload")
        public_key = tl_raw.get("public_key")
        if not token or not public_key:
            return []
        payload = self._decode(token, public_key)
        if not payload:
            return []
        results: List[dict] = []
        for event in payload.get("triggered_limits", []):
            if event.get("api_key_id") != api_key_id:
                continue
            if service_key and event.get("service_key") != service_key:
                continue
            if client_customer_key and event.get("client_customer_key") != client_customer_key:
                continue
            results.append(event)
        return results
