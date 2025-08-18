from __future__ import annotations

import configparser
import json
import os
import tempfile
import time
from contextlib import contextmanager


@contextmanager
def _file_lock(file_path: str):
    """Context manager for file locking to prevent race conditions."""
    if not file_path:
        yield
        return
    lock_file = f"{file_path}.lock"
    dir_path = os.path.dirname(file_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    max_retries = 10
    retry_delay = 0.1
    for attempt in range(max_retries):
        try:
            lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if attempt == max_retries - 1:
                try:
                    stat = os.stat(lock_file)
                    if time.time() - stat.st_mtime > 30:
                        os.unlink(lock_file)
                        continue
                except (OSError, FileNotFoundError):
                    pass
                raise RuntimeError(f"Could not acquire lock for {file_path}")
            time.sleep(retry_delay * (2 ** attempt))
    try:
        yield
    finally:
        try:
            os.close(lock_fd)
            os.unlink(lock_file)
        except (OSError, FileNotFoundError):
            pass


def _safe_read_config(ini_path: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser(allow_no_value=True, strict=False)
    if not os.path.exists(ini_path):
        return config
    try:
        config.read(ini_path)
        return config
    except configparser.DuplicateSectionError:
        _clean_duplicate_sections(ini_path)
        config = configparser.ConfigParser(allow_no_value=True, strict=False)
        config.read(ini_path)
        return config


def _clean_duplicate_sections(ini_path: str) -> None:
    if not os.path.exists(ini_path):
        return
    seen_sections: set[str] = set()
    cleaned_lines: list[str] = []
    current_section: str | None = None
    section_content: list[str] = []
    with open(ini_path, "r") as f:
        lines = f.readlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if current_section is not None:
                if current_section not in seen_sections:
                    cleaned_lines.extend(section_content)
                    seen_sections.add(current_section)
                section_content = []
            current_section = stripped
            section_content = [line]
        else:
            section_content.append(line)
    if current_section is not None and current_section not in seen_sections:
        cleaned_lines.extend(section_content)
    _atomic_write(ini_path, "".join(cleaned_lines))


def _atomic_write(file_path: str, content: str) -> None:
    if not file_path:
        return
    dir_path = os.path.dirname(file_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    temp_dir = dir_path if dir_path else "."
    temp_fd, temp_path = tempfile.mkstemp(dir=temp_dir, prefix=f".{os.path.basename(file_path)}.tmp")
    try:
        with os.fdopen(temp_fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.rename(temp_path, file_path)
    except Exception:
        try:
            os.unlink(temp_path)
        except (OSError, FileNotFoundError):
            pass
        raise



class IniManager:
    """Handle reading and writing triggered limits to the INI file."""

    def __init__(self, ini_path: str) -> None:
        self.ini_path = ini_path
        with _file_lock(self.ini_path):
            self._config = _safe_read_config(self.ini_path)

    def _write(self) -> None:
        with _file_lock(self.ini_path):
            import io
            content = io.StringIO()
            self._config.write(content)
            _atomic_write(self.ini_path, content.getvalue())

    def get_option(self, section: str, option: str, fallback: str | None = None) -> str | None:
        """Return ``option`` from ``section`` or ``fallback`` when missing."""
        with _file_lock(self.ini_path):
            config = _safe_read_config(self.ini_path)
        if config.has_section(section) and option in config[section]:
            return config[section][option]
        return fallback

    def set_option(self, section: str, option: str, value: str) -> None:
        """Persist ``option`` under ``section`` with ``value``."""
        with _file_lock(self.ini_path):
            cfg = _safe_read_config(self.ini_path)
            if section not in cfg:
                cfg.add_section(section)
            cfg[section][option] = str(value)
            import io
            buf = io.StringIO()
            cfg.write(buf)
            _atomic_write(self.ini_path, buf.getvalue())

    def read_triggered_limits(self) -> dict:
        with _file_lock(self.ini_path):
            self._config = _safe_read_config(self.ini_path)
        if (
            "triggered_limits" not in self._config
            or "payload" not in self._config["triggered_limits"]
        ):
            return {}
        return json.loads(self._config["triggered_limits"].get("payload", "{}"))

    def write_triggered_limits(self, data: dict) -> None:
        if "triggered_limits" in self._config:
            self._config.remove_section("triggered_limits")
        self._config.add_section("triggered_limits")
        self._config["triggered_limits"]["payload"] = json.dumps(data or {})
        self._write()
