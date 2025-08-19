from __future__ import annotations

import os
from dataclasses import dataclass, fields
from typing import Any

import httpx

from .ini_manager import IniManager
from .delivery import DeliveryType


def _to_bool(val: str) -> bool:
    return val.lower() in {"1", "true", "yes", "on"}


@dataclass
class TrackerConfig:
    """Configuration container for :class:`~aicostmanager.tracker.Tracker`."""

    ini_manager: IniManager
    delivery_type: DeliveryType | None = None
    aicm_api_key: str | None = None
    aicm_api_base: str | None = None
    aicm_api_url: str | None = None
    db_path: str | None = None
    log_file: str | None = None
    log_level: str | None = None
    timeout: float = 10.0
    poll_interval: float = 0.1
    batch_interval: float = 0.5
    max_attempts: int = 3
    max_retries: int = 5
    queue_size: int = 10000
    max_batch_size: int = 1000
    transport: httpx.BaseTransport | None = None
    log_bodies: bool = False

    @classmethod
    def from_env(
        cls,
        *,
        ini_manager: IniManager | None = None,
        aicm_ini_path: str | None = None,
        **overrides: Any,
    ) -> "TrackerConfig":
        """Load configuration from an INI file and environment variables.

        ``AICM_API_KEY`` is read from the environment (or ``overrides``) while the
        remaining options are loaded from ``[tracker]`` in the INI file.  Keyword
        arguments override values loaded from the INI file.
        """
        if ini_manager is None:
            ini_manager = IniManager(IniManager.resolve_path(aicm_ini_path))

        cfg = cls(ini_manager=ini_manager)
        parse_map: dict[str, Any] = {
            "timeout": float,
            "poll_interval": float,
            "batch_interval": float,
            "max_attempts": int,
            "max_retries": int,
            "queue_size": int,
            "max_batch_size": int,
            "log_bodies": _to_bool,
            "delivery_type": DeliveryType,
        }

        for f in fields(cls):
            if f.name == "ini_manager":
                continue
            if f.name == "aicm_api_key":
                val = overrides.get(f.name) or os.getenv("AICM_API_KEY")
                setattr(cfg, f.name, val)
                continue
            if f.name in overrides:
                setattr(cfg, f.name, overrides[f.name])
                continue
            ini_val = ini_manager.get_option("tracker", f.name, None)
            if ini_val is not None:
                parser = parse_map.get(f.name)
                if parser is not None:
                    ini_val = parser(ini_val)
                setattr(cfg, f.name, ini_val)
        return cfg
