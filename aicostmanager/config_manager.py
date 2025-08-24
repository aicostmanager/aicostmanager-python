from __future__ import annotations

import configparser
import json
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import jwt

from .client import AICMError, CostManagerClient
from .ini_manager import IniManager
from .triggered_limits_cache import triggered_limits_cache
from .utils.ini_utils import atomic_write, file_lock, safe_read_config


class ConfigNotFound(AICMError):
    """Raised when a requested config cannot be located."""


@dataclass
class Config:
    uuid: str
    config_id: str
    api_id: str
    last_updated: str
    handling_config: dict
    manual_usage_schema: Dict[str, str] | None = None


@dataclass
class TriggeredLimit:
    event_id: str
    limit_id: str
    threshold_type: str
    amount: float
    period: str
    config_id_list: Optional[List[str]]
    hostname: Optional[str]
    service_id: Optional[str]
    service_key: Optional[str]
    client_customer_key: Optional[str]
    api_key_id: str
    triggered_at: str
    expires_at: Optional[str]


class ConfigManager:
    """Manage tracker configuration and triggered limits stored in ``AICM.ini``."""

    def __init__(
        self,
        client: CostManagerClient | None = None,
        *,
        ini_path: str | None = None,
        get_triggered_limits: Callable[[], dict] | None = None,
        load: bool = True,
    ) -> None:
        if client is not None:
            self.ini_path = client.ini_path
            self._get_triggered_limits: Callable[[], dict] = client.get_triggered_limits
        else:
            if ini_path is None:
                ini_path = IniManager.resolve_path()
            if not ini_path:
                raise ValueError("ini_path could not be resolved")
            self.ini_path = ini_path
            self._get_triggered_limits = get_triggered_limits or (lambda: {})
        if load:
            with file_lock(self.ini_path):
                self._config = safe_read_config(self.ini_path)
        else:
            self._config = configparser.ConfigParser()

    def _write(self) -> None:
        """Safely write config with file locking."""
        with file_lock(self.ini_path):
            # Create content string
            import io

            content = io.StringIO()
            self._config.write(content)
            content_str = content.getvalue()

            # Atomic write
            atomic_write(self.ini_path, content_str)

    def _update_config(self, force_refresh_limits: bool = False) -> None:
        """Refresh triggered limits and persist to ``AICM.ini``."""
        if force_refresh_limits:
            try:
                tl_payload = self._get_triggered_limits() or {}
                if isinstance(tl_payload, dict):
                    tl_data = tl_payload.get("triggered_limits", tl_payload)
                    self._set_triggered_limits(tl_data)
                    self._write()
            except Exception:
                pass

    def _set_triggered_limits(self, data: dict) -> None:
        # Remove existing triggered_limits section if it exists
        if "triggered_limits" in self._config:
            self._config.remove_section("triggered_limits")
        self._config.add_section("triggered_limits")
        self._config["triggered_limits"]["payload"] = json.dumps(data or {})

    def write_triggered_limits(self, data: dict) -> None:
        """Persist ``triggered_limits`` payload to ``AICM.ini`` if changed."""
        existing = triggered_limits_cache.get_raw()
        if existing is None:
            try:
                existing = self.read_triggered_limits()
            except Exception:
                existing = None

        # Reuse stored public key when new data omits it
        if data and not data.get("public_key") and existing:
            pk = existing.get("public_key")
            if pk:
                data["public_key"] = pk

        if data == existing:
            token = data.get("encrypted_payload") if data else None
            public_key = data.get("public_key") if data else None
            if token and public_key:
                payload = self._decode(token, public_key)
                if payload:
                    triggered_limits_cache.set(
                        payload.get("triggered_limits", []), data
                    )
                else:
                    triggered_limits_cache.clear()
            else:
                triggered_limits_cache.clear()
            return

        self._set_triggered_limits(data)
        self._write()

        token = data.get("encrypted_payload")
        public_key = data.get("public_key")
        if token and public_key:
            payload = self._decode(token, public_key)
            if payload:
                triggered_limits_cache.set(
                    payload.get("triggered_limits", []), data
                )
            else:
                triggered_limits_cache.clear()
        else:
            triggered_limits_cache.clear()

    def read_triggered_limits(self) -> dict:
        """Return raw ``triggered_limits`` payload from ``AICM.ini``."""
        with file_lock(self.ini_path):
            self._config = safe_read_config(self.ini_path)
        if (
            "triggered_limits" not in self._config
            or "payload" not in self._config["triggered_limits"]
        ):
            return {}
        return json.loads(self._config["triggered_limits"].get("payload", "{}"))

    def refresh(self) -> None:
        """Force refresh of local configuration from the API."""
        self._update_config(force_refresh_limits=True)
        with file_lock(self.ini_path):
            self._config = safe_read_config(self.ini_path)

    # internal helper
    def _decode(self, token: str, public_key: str) -> Optional[dict]:
        try:
            return jwt.decode(
                token, public_key, algorithms=["RS256"], issuer="aicm-api"
            )
        except Exception:
            return None

    def get_config(self, api_id: str) -> List[Config]:
        """Return decrypted configs matching ``api_id``."""
        if "configs" not in self._config or "payload" not in self._config["configs"]:
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
                            manual_usage_schema=cfg.get("manual_usage_schema"),
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
                                manual_usage_schema=cfg.get("manual_usage_schema"),
                            )
                        )
            if not results:
                raise ConfigNotFound(f"No configuration found for api_id '{api_id}'")
        return results

    def get_config_by_id(self, config_id: str) -> Config:
        """Return decrypted config matching ``config_id``."""
        if "configs" not in self._config or "payload" not in self._config["configs"]:
            self.refresh()

        configs_raw = json.loads(self._config["configs"].get("payload", "[]"))
        for item in configs_raw:
            payload = self._decode(item["encrypted_payload"], item["public_key"])
            if not payload:
                continue
            for cfg in payload.get("configs", []):
                if cfg.get("config_id") == config_id:
                    return Config(
                        uuid=cfg.get("uuid"),
                        config_id=cfg.get("config_id"),
                        api_id=cfg.get("api_id"),
                        last_updated=cfg.get("last_updated"),
                        handling_config=cfg.get("handling_config", {}),
                        manual_usage_schema=cfg.get("manual_usage_schema"),
                    )

        # Refresh once if not found
        self.refresh()
        configs_raw = json.loads(self._config["configs"].get("payload", "[]"))
        for item in configs_raw:
            payload = self._decode(item["encrypted_payload"], item["public_key"])
            if not payload:
                continue
            for cfg in payload.get("configs", []):
                if cfg.get("config_id") == config_id:
                    return Config(
                        uuid=cfg.get("uuid"),
                        config_id=cfg.get("config_id"),
                        api_id=cfg.get("api_id"),
                        last_updated=cfg.get("last_updated"),
                        handling_config=cfg.get("handling_config", {}),
                        manual_usage_schema=cfg.get("manual_usage_schema"),
                    )

        raise ConfigNotFound(f"No configuration found for config_id '{config_id}'")

    def get_triggered_limits(
        self,
        service_id: Optional[str] = None,
        service_vendor: Optional[str] = None,
        client_customer_key: Optional[str] = None,
    ) -> List[TriggeredLimit]:
        """Return triggered limits for the given parameters."""
        events = triggered_limits_cache.get()
        if events is None:
            tl_raw = self.read_triggered_limits()
            token = tl_raw.get("encrypted_payload")
            public_key = tl_raw.get("public_key")

            if not token or not public_key:
                try:
                    tl_payload = self._get_triggered_limits() or {}
                    if isinstance(tl_payload, dict):
                        tl_data = tl_payload.get("triggered_limits", tl_payload)
                    else:
                        tl_data = tl_payload
                    self.write_triggered_limits(tl_data)
                except Exception:
                    return []
                events = triggered_limits_cache.get()
            else:
                payload = self._decode(token, public_key)
                if not payload:
                    triggered_limits_cache.clear()
                    return []
                events = payload.get("triggered_limits", [])
                triggered_limits_cache.set(events)

        if not events:
            return []
        results: List[TriggeredLimit] = []
        for event in events:
            vendor_info = event.get("vendor") or {}
            vendor_name = vendor_info.get("name")
            config_ids = vendor_info.get("config_ids")
            hostname = vendor_info.get("hostname")
            # Support legacy service_key field in addition to service_id/vendor
            legacy_service_key = event.get("service_key")
            legacy_vendor = legacy_service_id = None
            if isinstance(legacy_service_key, str) and "::" in legacy_service_key:
                legacy_vendor, legacy_service_id = legacy_service_key.split("::", 1)

            matches_service = (
                (
                    (
                        service_id
                        and (
                            event.get("service_id") == service_id
                            or legacy_service_id == service_id
                        )
                    )
                    or (
                        service_vendor
                        and (
                            vendor_name == service_vendor
                            or legacy_vendor == service_vendor
                        )
                    )
                )
                if (service_id or service_vendor)
                else True
            )

            matches_client = (
                (
                    client_customer_key
                    and event.get("client_customer_key") == client_customer_key
                )
                if client_customer_key
                else True
            )

            if matches_service and matches_client:
                # Prefer explicit service_key from event if provided. Fallback
                # to composing from vendor name and service_id for matching.
                sk = event.get("service_key")
                if not sk:
                    sid_for_key = event.get("service_id") or legacy_service_id
                    if vendor_name and sid_for_key:
                        sk = f"{vendor_name}::{sid_for_key}"
                results.append(
                    TriggeredLimit(
                        event_id=event.get("event_id"),
                        limit_id=event.get("limit_id"),
                        threshold_type=event.get("threshold_type"),
                        amount=float(event.get("amount", 0)),
                        period=event.get("period"),
                        config_id_list=config_ids,
                        hostname=hostname,
                        service_id=event.get("service_id") or legacy_service_id,
                        service_key=sk,
                        client_customer_key=event.get("client_customer_key"),
                        api_key_id=event.get("api_key_id"),
                        triggered_at=event.get("triggered_at"),
                        expires_at=event.get("expires_at"),
                    )
                )
        return results
