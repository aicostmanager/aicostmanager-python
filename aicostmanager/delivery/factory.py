from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Delivery, DeliveryConfig, DeliveryType
from .immediate import ImmediateDelivery
from .mem_queue import MemQueueDelivery
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
        DeliveryType.MEM_QUEUE: MemQueueDelivery,
        DeliveryType.PERSISTENT_QUEUE: PersistentDelivery,
    }
    if delivery_type not in factory:
        raise ValueError(f"Unsupported delivery type: {delivery_type}")

    if delivery_type is DeliveryType.MEM_QUEUE:
        params = {
            "queue_size": kwargs.get("queue_size", 10000),
            "batch_interval": kwargs.get("batch_interval", 0.5),
            "max_batch_size": kwargs.get("max_batch_size", 1000),
            "max_retries": kwargs.get("max_retries", 5),
        }
        return MemQueueDelivery(config, **params)
    if delivery_type is DeliveryType.PERSISTENT_QUEUE:
        db_path = kwargs.get("db_path") or str(
            Path.home() / ".cache" / "aicostmanager" / "delivery_queue.db"
        )
        log_bodies = kwargs.get("log_bodies", False)
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
