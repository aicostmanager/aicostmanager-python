from __future__ import annotations

from pathlib import Path
from typing import Any
import os

from .base import Delivery, DeliveryConfig, DeliveryType
from .immediate import ImmediateDelivery
from .persistent import PersistentDelivery


def create_delivery(delivery_type: DeliveryType, config: DeliveryConfig, **kwargs: Any) -> Delivery:
    """Create a delivery instance based on ``delivery_type``.

    Parameters
    ----------
    delivery_type:
        The desired delivery strategy.
    config:
        Shared delivery configuration.
    **kwargs:
        Additional delivery specific options.
    """
    factory = {
        DeliveryType.IMMEDIATE: ImmediateDelivery,
        DeliveryType.PERSISTENT_QUEUE: PersistentDelivery,
    }
    if delivery_type not in factory:
        raise ValueError(f"Unsupported delivery type: {delivery_type}")

    if delivery_type is DeliveryType.PERSISTENT_QUEUE:
        db_path = kwargs.get("db_path") or str(
            Path.home() / ".cache" / "aicostmanager" / "delivery_queue.db"
        )
        log_bodies = kwargs.get("log_bodies")
        if log_bodies is None:
            env_val = os.getenv("AICM_LOG_BODIES") or os.getenv(
                "AICM_DELIVERY_LOG_BODIES"
            )
            log_bodies = str(env_val).lower() in {"1", "true", "yes", "on"}
        else:
            log_bodies = bool(log_bodies)
        params = {
            "db_path": db_path,
            "poll_interval": kwargs.get("poll_interval", 0.1),
            "batch_interval": kwargs.get("batch_interval", 0.5),
            "max_attempts": kwargs.get("max_attempts", 3),
            "max_retries": kwargs.get("max_retries", 5),
            "log_bodies": log_bodies,
            "max_batch_size": kwargs.get("max_batch_size", 1000),
        }
        return PersistentDelivery(config=config, **params)
    return ImmediateDelivery(config)
