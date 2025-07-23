from __future__ import annotations

import configparser
import json
import os
from dataclasses import dataclass
from typing import List, Optional

import jwt

from .client import CostManagerClient, AICMError


class ConfigNotFound(AICMError):
    """Raised when a requested config cannot be located."""


@dataclass
class Config:
    uuid: str
    config_id: str
    api_id: str
    last_updated: str
    handling_config: dict


@dataclass
class TriggeredLimit:
    event_id: str
    limit_id: str
    threshold_type: str
    amount: float
    period: str
    vendor: Optional[str]
    service_id: Optional[str]
    client_customer_key: Optional[str]
    api_key_id: str
    triggered_at: str
    expires_at: Optional[str]


class CostManagerConfig:
    """Manage tracker configuration and triggered limits stored in ``AICM.ini``."""

    def __init__(self, client: CostManagerClient, *, auto_refresh: bool = False) -> None:
        self.client = client
        self.ini_path = client.ini_path
        self.auto_refresh = auto_refresh
        self._config = configparser.ConfigParser()
        self._config.read(self.ini_path)

    def _write(self) -> None:
        os.makedirs(os.path.dirname(self.ini_path), exist_ok=True)
        with open(self.ini_path, "w") as f:
            self._config.write(f)

    def _update_config(self) -> None:
        """Fetch configs from the API and persist to ``AICM.ini``."""
        data = self.client.get_configs()
        if hasattr(data, "model_dump"):
            payload = data.model_dump()
        else:
            payload = data
        self._config["configs"] = {
            "payload": json.dumps(payload.get("service_configs", []))
        }
        self._config["triggered_limits"] = {
            "payload": json.dumps(payload.get("triggered_limits", {}))
        }
        self._write()

    def refresh(self) -> None:
        """Force refresh of local configuration from the API."""
        self._update_config()
        self._config.read(self.ini_path)

    # internal helper
    def _decode(self, token: str, public_key: str) -> Optional[dict]:
        try:
            return jwt.decode(token, public_key, algorithms=["RS256"], issuer="aicm-api")
        except Exception:
            return None

    def get_config(self, api_id: str) -> List[Config]:
        """Return decrypted configs matching ``api_id``."""
        if self.auto_refresh or "configs" not in self._config or "payload" not in self._config["configs"]:
            self.refresh()

        configs_raw = json.loads(self._config["configs"].get("payload", "[]"))
        results: List[Config] = []
        for item in configs_raw:
            payload = self._decode(item["encrypted_payload"], item["public_key"])
            if not payload:
                continue
            for cfg in payload.get("configs", []):
                if cfg.get("api_id") == api_id:
                    results.append(
                        Config(
                            uuid=cfg.get("uuid"),
                            config_id=cfg.get("config_id"),
                            api_id=cfg.get("api_id"),
                            last_updated=cfg.get("last_updated"),
                            handling_config=cfg.get("handling_config", {}),
                        )
                    )

        if not results:
            # refresh once
            self.refresh()
            configs_raw = json.loads(self._config["configs"].get("payload", "[]"))
            for item in configs_raw:
                payload = self._decode(item["encrypted_payload"], item["public_key"])
                if not payload:
                    continue
                for cfg in payload.get("configs", []):
                    if cfg.get("api_id") == api_id:
                        results.append(
                            Config(
                                uuid=cfg.get("uuid"),
                                config_id=cfg.get("config_id"),
                                api_id=cfg.get("api_id"),
                                last_updated=cfg.get("last_updated"),
                                handling_config=cfg.get("handling_config", {}),
                            )
                        )
            if not results:
                raise ConfigNotFound(f"No configuration found for api_id '{api_id}'")
        return results

    def get_triggered_limits(
        self,
        service_id: Optional[str] = None,
        service_vendor: Optional[str] = None,
        client_customer_key: Optional[str] = None,
    ) -> List[TriggeredLimit]:
        """Return triggered limits for the given parameters."""
        if self.auto_refresh or "triggered_limits" not in self._config or "payload" not in self._config["triggered_limits"]:
            self.refresh()

        tl_raw = json.loads(self._config["triggered_limits"].get("payload", "{}"))
        token = tl_raw.get("encrypted_payload")
        public_key = tl_raw.get("public_key")
        if not token or not public_key:
            return []
        payload = self._decode(token, public_key)
        if not payload:
            return []
        events = payload.get("triggered_limits", [])
        results: List[TriggeredLimit] = []
        for event in events:
            if (
                service_id
                and event.get("service_id") == service_id
                or service_vendor
                and event.get("vendor") == service_vendor
                or client_customer_key
                and event.get("client_customer_key") == client_customer_key
                or (not service_id and not service_vendor and not client_customer_key)
            ):
                results.append(
                    TriggeredLimit(
                        event_id=event.get("event_id"),
                        limit_id=event.get("limit_id"),
                        threshold_type=event.get("threshold_type"),
                        amount=float(event.get("amount", 0)),
                        period=event.get("period"),
                        vendor=event.get("vendor"),
                        service_id=event.get("service_id"),
                        client_customer_key=event.get("client_customer_key"),
                        api_key_id=event.get("api_key_id"),
                        triggered_at=event.get("triggered_at"),
                        expires_at=event.get("expires_at"),
                    )
                )
        return results
