from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict


class DeliveryType(str, Enum):
    IMMEDIATE = "immediate"
    MEM_QUEUE = "mem_queue"
    PERSISTENT_QUEUE = "persistent_queue"


class Delivery(ABC):
    """Abstract base class for tracker delivery mechanisms."""

    def __init__(
        self,
        *,
        log_file: str | None = None,
        log_level: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        log_file = log_file or os.getenv("AICM_DELIVERY_LOG_FILE")
        log_level = (log_level or os.getenv("AICM_DELIVERY_LOG_LEVEL", "INFO")).upper()
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))
        if not self.logger.handlers:
            handler = logging.FileHandler(log_file) if log_file else logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    @abstractmethod
    def enqueue(self, payload: Dict[str, Any]) -> None:
        """Queue ``payload`` for background delivery."""

    def stop(self) -> None:  # pragma: no cover - default no-op
        """Shutdown any background resources."""
        return None
