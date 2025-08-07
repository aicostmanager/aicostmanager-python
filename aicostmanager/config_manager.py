from __future__ import annotations

import configparser
import json
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, List, Optional

import jwt

from .client import AICMError, CostManagerClient


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
    client_customer_key: Optional[str]
    api_key_id: str
    triggered_at: str
    expires_at: Optional[str]


@contextmanager
def _file_lock(file_path: str):
    """Context manager for file locking to prevent race conditions."""
    # Handle empty or None file paths
    if not file_path:
        yield
        return

    lock_file = f"{file_path}.lock"

    # Handle directory creation more carefully
    dir_path = os.path.dirname(file_path)
    if dir_path:  # Only create directory if it's not empty
        os.makedirs(dir_path, exist_ok=True)

    # Retry mechanism for lock acquisition
    max_retries = 10
    retry_delay = 0.1

    for attempt in range(max_retries):
        try:
            lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if attempt == max_retries - 1:
                # Force remove stale lock if it's too old (>30 seconds)
                try:
                    stat = os.stat(lock_file)
                    if time.time() - stat.st_mtime > 30:
                        os.unlink(lock_file)
                        continue
                except (OSError, FileNotFoundError):
                    pass
                raise RuntimeError(f"Could not acquire lock for {file_path}")
            time.sleep(retry_delay * (2**attempt))  # Exponential backoff

    try:
        yield
    finally:
        try:
            os.close(lock_fd)
            os.unlink(lock_file)
        except (OSError, FileNotFoundError):
            pass


def _safe_read_config(ini_path: str) -> configparser.ConfigParser:
    """Safely read a ConfigParser, handling duplicate sections."""
    config = configparser.ConfigParser(allow_no_value=True, strict=False)

    if not os.path.exists(ini_path):
        return config

    # Read and clean the INI file if it has duplicates
    try:
        config.read(ini_path)
        return config
    except configparser.DuplicateSectionError:
        # Handle duplicate sections by cleaning the file
        _clean_duplicate_sections(ini_path)
        config = configparser.ConfigParser(allow_no_value=True, strict=False)
        config.read(ini_path)
        return config


def _clean_duplicate_sections(ini_path: str):
    """Remove duplicate sections from INI file, keeping the last occurrence."""
    if not os.path.exists(ini_path):
        return

    # Read the file and remove duplicates
    seen_sections = set()
    cleaned_lines = []
    current_section = None
    section_content = []

    with open(ini_path, "r") as f:
        lines = f.readlines()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            # Found a section header
            if current_section is not None:
                # Save previous section if it's the first occurrence
                if current_section not in seen_sections:
                    cleaned_lines.extend(section_content)
                    seen_sections.add(current_section)
                section_content = []

            current_section = stripped
            section_content = [line]
        else:
            section_content.append(line)

    # Handle the last section
    if current_section is not None:
        if current_section not in seen_sections:
            cleaned_lines.extend(section_content)

    # Write cleaned content atomically
    _atomic_write(ini_path, "".join(cleaned_lines))


def _atomic_write(file_path: str, content: str):
    """Atomically write content to a file."""
    # Handle empty or None file paths
    if not file_path:
        return

    # Handle directory creation more carefully
    dir_path = os.path.dirname(file_path)
    if dir_path:  # Only create directory if it's not empty
        os.makedirs(dir_path, exist_ok=True)

    # Write to a temporary file first
    temp_dir = dir_path if dir_path else "."  # Use current directory if no dir_path
    temp_fd, temp_path = tempfile.mkstemp(
        dir=temp_dir, prefix=f".{os.path.basename(file_path)}.tmp"
    )

    try:
        with os.fdopen(temp_fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # Atomic rename
        os.rename(temp_path, file_path)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except (OSError, FileNotFoundError):
            pass
        raise


class CostManagerConfig:
    """Manage tracker configuration and triggered limits stored in ``AICM.ini``."""

    def __init__(self, client: CostManagerClient) -> None:
        self.client = client
        self.ini_path = client.ini_path

        # Initialize with safe reading
        with _file_lock(self.ini_path):
            self._config = _safe_read_config(self.ini_path)

    def _write(self) -> None:
        """Safely write config with file locking."""
        with _file_lock(self.ini_path):
            # Create content string
            import io

            content = io.StringIO()
            self._config.write(content)
            content_str = content.getvalue()

            # Atomic write
            _atomic_write(self.ini_path, content_str)

    def _update_config(self, force_refresh_limits: bool = False) -> None:
        """Fetch configs from the API and persist to ``AICM.ini``."""
        etag = None
        if self._config.has_section("configs"):
            etag = self._config["configs"].get("etag")

        data = self.client.get_configs(etag=etag)
        if data is None:
            # Config unchanged - only refresh triggered limits if explicitly requested (via refresh())
            if force_refresh_limits:
                try:
                    tl_payload = self.client.get_triggered_limits() or {}
                    if isinstance(tl_payload, dict):
                        tl_data = tl_payload.get("triggered_limits", tl_payload)
                        self._set_triggered_limits(tl_data)
                        self._write()
                except Exception:
                    pass
            return

        if hasattr(data, "model_dump"):
            payload = data.model_dump(mode="json")
        else:
            payload = data

        self._config["configs"] = {
            "payload": json.dumps(payload.get("service_configs", [])),
            "etag": self.client.configs_etag or "",
        }

        # Always update triggered_limits when configs change (same logic as client initialization)
        try:
            tl_payload = payload.get("triggered_limits")
            if tl_payload is not None:
                # Use triggered_limits from configs response
                if isinstance(tl_payload, dict):
                    tl_data = tl_payload.get("triggered_limits", tl_payload)
                else:
                    tl_data = tl_payload
                self._set_triggered_limits(tl_data)
            else:
                # Configs response didn't include triggered_limits, fetch separately
                try:
                    tl_response = self.client.get_triggered_limits() or {}
                    if isinstance(tl_response, dict):
                        tl_data = tl_response.get("triggered_limits", tl_response)
                    else:
                        tl_data = tl_response
                    self._set_triggered_limits(tl_data)
                except Exception:
                    # Don't fail if triggered limits fetch fails
                    pass
        except Exception:
            # Don't fail config update if triggered limits update fails
            pass

        self._write()

    def _set_triggered_limits(self, data: dict) -> None:
        # Remove existing triggered_limits section if it exists
        if "triggered_limits" in self._config:
            self._config.remove_section("triggered_limits")
        self._config.add_section("triggered_limits")
        self._config["triggered_limits"]["payload"] = json.dumps(data or {})

    def store_triggered_limits(self, data: dict) -> None:
        """Persist ``triggered_limits`` payload to ``AICM.ini``."""
        self._set_triggered_limits(data)
        self._write()

    def refresh(self) -> None:
        """Force refresh of local configuration from the API."""
        self._update_config(force_refresh_limits=True)
        with _file_lock(self.ini_path):
            self._config = _safe_read_config(self.ini_path)

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
        # Always re-read INI file to get latest triggered_limits from delivery worker updates
        with _file_lock(self.ini_path):
            self._config = _safe_read_config(self.ini_path)

        if (
            "triggered_limits" not in self._config
            or "payload" not in self._config["triggered_limits"]
        ):
            self.refresh()
            with _file_lock(self.ini_path):
                self._config = _safe_read_config(self.ini_path)

        tl_raw = json.loads(self._config["triggered_limits"].get("payload", "{}"))
        token = tl_raw.get("encrypted_payload")
        public_key = tl_raw.get("public_key")

        # If INI doesn't contain encrypted payload, fetch directly from API
        if not token or not public_key:
            try:
                tl_payload = self.client.get_triggered_limits() or {}
                if isinstance(tl_payload, dict):
                    tl_data = tl_payload.get("triggered_limits", tl_payload)
                else:
                    tl_data = tl_payload
                self.store_triggered_limits(tl_data)
                with _file_lock(self.ini_path):
                    self._config = _safe_read_config(self.ini_path)
                tl_raw = json.loads(self._config["triggered_limits"].get("payload", "{}"))
                token = tl_raw.get("encrypted_payload")
                public_key = tl_raw.get("public_key")
            except Exception:
                return []

        if not token or not public_key:
            return []

        payload = self._decode(token, public_key)
        if not payload:
            return []
        events = payload.get("triggered_limits", [])
        results: List[TriggeredLimit] = []
        for event in events:
            vendor_info = event.get("vendor") or {}
            vendor_name = vendor_info.get("name")
            config_ids = vendor_info.get("config_ids")
            hostname = vendor_info.get("hostname")
            if (
                service_id
                and event.get("service_id") == service_id
                or service_vendor
                and vendor_name == service_vendor
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
                        config_id_list=config_ids,
                        hostname=hostname,
                        service_id=event.get("service_id"),
                        client_customer_key=event.get("client_customer_key"),
                        api_key_id=event.get("api_key_id"),
                        triggered_at=event.get("triggered_at"),
                        expires_at=event.get("expires_at"),
                    )
                )
        return results
