from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .exceptions import MissingConfiguration


class BaseClient:
    """Shared initialization logic for SDK clients."""

    def __init__(
        self,
        *,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        aicm_ini_path: Optional[str] = None,
    ) -> None:
        self.api_key = aicm_api_key or os.getenv("AICM_API_KEY")
        self.api_base = aicm_api_base or os.getenv(
            "AICM_API_BASE", "https://aicostmanager.com"
        )
        self.api_url = aicm_api_url or os.getenv("AICM_API_URL", "/api/v1")
        self.ini_path = (
            aicm_ini_path
            or os.getenv("AICM_INI_PATH")
            or str(Path.home() / ".config" / "aicostmanager" / "AICM.INI")
        )
        if not self.api_key:
            raise MissingConfiguration(
                "API key not provided. Set AICM_API_KEY environment variable or pass aicm_api_key"
            )

    @property
    def api_root(self) -> str:
        """Return the combined AICostManager API base URL."""
        return self.api_base.rstrip("/") + self.api_url

    def _store_triggered_limits(self, triggered_limits_response) -> None:
        """Persist triggered limits using the configuration manager."""
        from ..config_manager import ConfigManager

        cfg_mgr = ConfigManager(ini_path=self.ini_path)
        if isinstance(triggered_limits_response, dict):
            tl_data = triggered_limits_response.get(
                "triggered_limits", triggered_limits_response
            )
        else:
            tl_data = triggered_limits_response
        cfg_mgr.write_triggered_limits(tl_data)
