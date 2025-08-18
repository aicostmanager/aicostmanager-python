from __future__ import annotations

import os
from pathlib import Path

from .utils.ini_utils import atomic_write, file_lock, safe_read_config


class IniManager:
    """Helper for reading and writing generic values to ``AICM.ini``."""

    def __init__(self, ini_path: str | None = None) -> None:
        self.ini_path = self.resolve_path(ini_path)
        with file_lock(self.ini_path):
            self._config = safe_read_config(self.ini_path)

    @classmethod
    def resolve_path(cls, ini_path: str | None = None) -> str:
        """Resolve the path to the INI file."""
        return ini_path or os.getenv(
            "AICM_INI_PATH", str(Path.home() / ".config" / "aicostmanager" / "AICM.INI")
        )

    def _write(self) -> None:
        with file_lock(self.ini_path):
            import io
            content = io.StringIO()
            self._config.write(content)
            atomic_write(self.ini_path, content.getvalue())

    def get_option(self, section: str, option: str, fallback: str | None = None) -> str | None:
        """Return ``option`` from ``section`` or ``fallback`` when missing."""
        with file_lock(self.ini_path):
            config = safe_read_config(self.ini_path)
        if config.has_section(section) and option in config[section]:
            return config[section][option]
        return fallback

    def set_option(self, section: str, option: str, value: str) -> None:
        """Persist ``option`` under ``section`` with ``value``."""
        with file_lock(self.ini_path):
            cfg = safe_read_config(self.ini_path)
            if section not in cfg:
                cfg.add_section(section)
            cfg[section][option] = str(value)
            import io
            buf = io.StringIO()
            cfg.write(buf)
            atomic_write(self.ini_path, buf.getvalue())
