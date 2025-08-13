from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from uuid import uuid4

from .persistent_delivery import PersistentDelivery


class Tracker:
    """Lightweight usage tracker for the new ``/track`` endpoint."""

    def __init__(
        self,
        *,
        delivery: PersistentDelivery | None = None,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        aicm_ini_path: Optional[str] = None,
        db_path: Optional[str] = None,
        log_file: Optional[str] = None,
        log_level: Optional[str] = None,
        timeout: float = 10.0,
        poll_interval: float = 1.0,
        max_attempts: int = 3,
        max_retries: int = 5,
    ) -> None:
        if delivery is not None:
            self.delivery = delivery
        else:
            self.delivery = PersistentDelivery(
                aicm_api_key=aicm_api_key,
                aicm_api_base=aicm_api_base,
                aicm_api_url=aicm_api_url,
                aicm_ini_path=aicm_ini_path,
                db_path=db_path,
                log_file=log_file,
                log_level=log_level,
                timeout=timeout,
                poll_interval=poll_interval,
                max_attempts=max_attempts,
                max_retries=max_retries,
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
            "service_key": system_key,
            "response_id": response_id or uuid4().hex,
            "timestamp": (
                timestamp.isoformat()
                if isinstance(timestamp, datetime)
                else timestamp or datetime.now(timezone.utc).isoformat()
            ),
            "payload": usage,
        }
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
    def sync_track(
        self,
        api_id: str,
        system_key: str,
        usage: Dict[str, Any],
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Immediately deliver a usage record, bypassing the queue."""
        record = self._build_record(
            api_id,
            system_key,
            usage,
            response_id=response_id,
            timestamp=timestamp,
            client_customer_key=client_customer_key,
            context=context,
        )
        return self.delivery.deliver_now(record)

    async def sync_track_async(
        self,
        api_id: str,
        system_key: str,
        usage: Dict[str, Any],
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        record = self._build_record(
            api_id,
            system_key,
            usage,
            response_id=response_id,
            timestamp=timestamp,
            client_customer_key=client_customer_key,
            context=context,
        )
        return await self.delivery.deliver_now_async(record)

    # Backwards compatible aliases
    track_sync = sync_track
    track_sync_async = sync_track_async

    # ------------------------------------------------------------------
    def close(self) -> None:
        self.delivery.stop()
