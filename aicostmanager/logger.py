"""Logging utilities for aicostmanager."""

from __future__ import annotations

import logging
import os


def create_logger(
    name: str,
    log_file: str | None = None,
    log_level: str | None = None,
    log_file_env: str = "AICM_LOG_FILE",
    log_level_env: str = "AICM_LOG_LEVEL",
) -> logging.Logger:
    """Return a configured :class:`logging.Logger`."""
    log_file = log_file or os.getenv(log_file_env)
    level = (log_level or os.getenv(log_level_env, "INFO")).upper()
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level, logging.INFO))
    if not logger.handlers:
        handler = logging.FileHandler(log_file) if log_file else logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
