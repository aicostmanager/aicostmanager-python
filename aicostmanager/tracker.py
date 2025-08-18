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
from .usage_utils import (
    get_streaming_usage_from_response,
    get_usage_from_response,
)


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
        self.ini_manager = ini_manager or IniManager(
            IniManager.resolve_path(aicm_ini_path)
        )
        self.logger = create_logger(
            __name__,
            log_file,
            log_level,
            "AICM_TRACKER_LOG_FILE",
            "AICM_TRACKER_LOG_LEVEL",
        )
        if delivery is not None:
            self.delivery = delivery
            delivery_type = getattr(
                delivery, "type", delivery_type or DeliveryType.IMMEDIATE
            )
        else:
            if delivery_type is None:
                # If a db_path is provided, prefer persistent queue by default
                if db_path:
                    delivery_type = DeliveryType.PERSISTENT_QUEUE
                else:
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
        system_key: Optional[str],
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
        system_key: Optional[str],
        usage: Dict[str, Any],
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Enqueue a usage record for background delivery.

        Returns the ``response_id`` that will be used for this record. If none was
        provided, a new UUID4 hex value is generated and returned.
        """
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
        return record["response_id"]

    async def track_async(
        self,
        api_id: str,
        system_key: Optional[str],
        usage: Dict[str, Any],
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        return await asyncio.to_thread(
            self.track,
            api_id,
            system_key,
            usage,
            response_id=response_id,
            timestamp=timestamp,
            client_customer_key=client_customer_key,
            context=context,
        )

    def track_llm_usage(
        self,
        api_id: str,
        response: Any,
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Extract usage from an LLM response and enqueue it.

        Parameters are identical to :meth:`track` except that ``response`` is
        the raw LLM client response.  Usage information is obtained via
        :func:`get_usage_from_response` using the provided ``api_id``.
        ``response`` is returned to allow call chaining. If a ``response_id`` was
        not provided and one is generated, it is attached to the response as
        ``response.aicm_response_id`` for convenience.
        """
        usage = get_usage_from_response(response, api_id)
        if isinstance(usage, dict) and usage:
            model = getattr(response, "model", None)
            vendor_map = {
                "openai_chat": "openai",
                "openai_responses": "openai",
                "anthropic": "anthropic",
                "gemini": "google",
            }
            vendor_prefix = vendor_map.get(api_id)
            system_key = (
                f"{vendor_prefix}::{model}" if vendor_prefix and model else model
            )
            used_response_id = self.track(
                api_id,
                system_key,
                usage,
                response_id=response_id,
                timestamp=timestamp,
                client_customer_key=client_customer_key,
                context=context,
            )
            try:
                # Attach for caller convenience
                setattr(response, "aicm_response_id", used_response_id)
            except Exception:
                pass
        return response

    async def track_llm_usage_async(
        self,
        api_id: str,
        response: Any,
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Async version of :meth:`track_llm_usage`."""
        return await asyncio.to_thread(
            self.track_llm_usage,
            api_id,
            response,
            response_id=response_id,
            timestamp=timestamp,
            client_customer_key=client_customer_key,
            context=context,
        )

    def track_llm_stream_usage(
        self,
        api_id: str,
        stream: Any,
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Yield streaming events while tracking usage.

        ``stream`` should be an iterable of events from an LLM SDK.  Usage
        information is extracted from events using
        :func:`get_streaming_usage_from_response` and sent via :meth:`track` once
        available.
        """
        model = getattr(stream, "model", None)
        vendor_map = {
            "openai_chat": "openai",
            "openai_responses": "openai",
            "anthropic": "anthropic",
            "gemini": "google",
        }
        vendor_prefix = vendor_map.get(api_id)
        system_key = f"{vendor_prefix}::{model}" if vendor_prefix and model else model
        usage_sent = False
        for chunk in stream:
            if not usage_sent:
                usage = get_streaming_usage_from_response(chunk, api_id)
                if isinstance(usage, dict) and usage:
                    self.track(
                        api_id,
                        system_key,
                        usage,
                        response_id=response_id,
                        timestamp=timestamp,
                        client_customer_key=client_customer_key,
                        context=context,
                    )
                    usage_sent = True
            yield chunk

    async def track_llm_stream_usage_async(
        self,
        api_id: str,
        stream: Any,
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Asynchronous version of :meth:`track_llm_stream_usage`."""
        system_key = getattr(stream, "model", None)
        usage_sent = False
        async for chunk in stream:
            if not usage_sent:
                usage = get_streaming_usage_from_response(chunk, api_id)
                if isinstance(usage, dict) and usage:
                    await self.track_async(
                        api_id,
                        system_key,
                        usage,
                        response_id=response_id,
                        timestamp=timestamp,
                        client_customer_key=client_customer_key,
                        context=context,
                    )
                    usage_sent = True
            yield chunk

    # ------------------------------------------------------------------
    def __enter__(self):
        """Context manager entry point."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point - automatically closes the tracker."""
        self.close()

    def close(self) -> None:
        self.delivery.stop()
