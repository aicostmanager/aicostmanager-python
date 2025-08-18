from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

import httpx

from .delivery import (
    Delivery,
    DeliveryConfig,
    DeliveryType,
    create_delivery,
)
from .ini_manager import IniManager
from .logger import create_logger


class Tracker:
    """Lightweight usage tracker for the new ``/track`` endpoint."""

    def __init__(
        self,
        *,
        delivery_type: DeliveryType | None = None,
        delivery: Delivery | None = None,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        aicm_ini_path: Optional[str] = None,
        ini_manager: IniManager | None = None,
        db_path: Optional[str] = None,
        log_file: Optional[str] = None,
        log_level: Optional[str] = None,
        timeout: float = 10.0,
        poll_interval: float = 0.1,
        batch_interval: float = 0.5,
        max_attempts: int = 3,
        max_retries: int = 5,
        queue_size: int = 10000,
        max_batch_size: int = 1000,
        transport: httpx.BaseTransport | None = None,
        log_bodies: bool = False,
    ) -> None:
        self.ini_manager = ini_manager or IniManager(IniManager.resolve_path(aicm_ini_path))
        self.logger = create_logger(
            __name__, log_file, log_level, "AICM_TRACKER_LOG_FILE", "AICM_TRACKER_LOG_LEVEL"
        )
        if delivery is not None:
            self.delivery = delivery
            delivery_type = getattr(delivery, "type", delivery_type or DeliveryType.IMMEDIATE)
        else:
            if delivery_type is None:
                name = self.ini_manager.get_option(
                    "tracker", "delivery_manager", DeliveryType.IMMEDIATE.value
                )
                delivery_type = DeliveryType(name)
            config = DeliveryConfig(
                ini_manager=self.ini_manager,
                aicm_api_key=aicm_api_key,
                aicm_api_base=aicm_api_base,
                aicm_api_url=aicm_api_url,
                timeout=timeout,
                transport=transport,
                log_file=log_file,
                log_level=log_level,
            )
            self.delivery = create_delivery(
                delivery_type,
                config,
                db_path=db_path,
                poll_interval=poll_interval,
                batch_interval=batch_interval,
                max_attempts=max_attempts,
                max_retries=max_retries,
                queue_size=queue_size,
                max_batch_size=max_batch_size,
                log_bodies=log_bodies,
            )
        if delivery_type is not None:
            self.ini_manager.set_option(
                "tracker", "delivery_manager", delivery_type.value
            )

    # ------------------------------------------------------------------
    def _build_record(
        self,
        api_id: str,
        system_key: str,
        usage: Dict[str, Any],
        *,
        response_id: Optional[str],
        timestamp: str | datetime | None,
        client_customer_key: Optional[str],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "api_id": api_id,
            "response_id": response_id or uuid4().hex,
            "timestamp": (
                timestamp.isoformat()
                if isinstance(timestamp, datetime)
                else timestamp or datetime.now(timezone.utc).isoformat()
            ),
            "payload": usage,
        }
        # Only include service_key when provided. Some server-side validators
        # treat explicit null differently from an omitted field.
        if system_key is not None:
            record["service_key"] = system_key
        if client_customer_key is not None:
            record["client_customer_key"] = client_customer_key
        if context is not None:
            record["context"] = context
        return record

    # ------------------------------------------------------------------
    def track(
        self,
        api_id: str,
        system_key: str,
        usage: Dict[str, Any],
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Enqueue a usage record for background delivery."""
        record = self._build_record(
            api_id,
            system_key,
            usage,
            response_id=response_id,
            timestamp=timestamp,
            client_customer_key=client_customer_key,
            context=context,
        )
        self.delivery.enqueue(record)

    async def track_async(
        self,
        api_id: str,
        system_key: str,
        usage: Dict[str, Any],
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        await asyncio.to_thread(
            self.track,
            api_id,
            system_key,
            usage,
            response_id=response_id,
            timestamp=timestamp,
            client_customer_key=client_customer_key,
            context=context,
        )

    # ------------------------------------------------------------------
    def __enter__(self):
        """Context manager entry point."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point - automatically closes the tracker."""
        self.close()

    def close(self) -> None:
        self.delivery.stop()
