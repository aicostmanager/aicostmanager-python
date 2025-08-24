from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

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
        aicm_api_key: str | None = None,
        ini_path: str | None = None,
        delivery: Delivery | None = None,
    ) -> None:
        self.ini_manager = IniManager(IniManager.resolve_path(ini_path))
        self.ini_path = self.ini_manager.ini_path
        self.aicm_api_key = aicm_api_key or os.getenv("AICM_API_KEY")

        def _get(option: str, default: str | None = None) -> str | None:
            val = self.ini_manager.get_option("tracker", option)
            if val is not None:
                return val
            return os.getenv(option, default)

        api_base = _get("AICM_API_BASE", "https://aicostmanager.com")
        api_url = _get("AICM_API_URL", "/api/v1")
        db_path = _get("AICM_DB_PATH")
        log_file = _get("AICM_LOG_FILE")
        log_level = _get("AICM_LOG_LEVEL")
        timeout = float(_get("AICM_TIMEOUT", "10.0"))
        poll_interval = float(_get("AICM_POLL_INTERVAL", "0.1"))
        batch_interval = float(_get("AICM_BATCH_INTERVAL", "0.5"))
        immediate_pause_seconds = float(
            _get("AICM_IMMEDIATE_PAUSE_SECONDS", "5.0")
        )
        max_attempts = int(_get("AICM_MAX_ATTEMPTS", "3"))
        max_retries = int(_get("AICM_MAX_RETRIES", "5"))
        max_batch_size = int(_get("AICM_MAX_BATCH_SIZE", "1000"))
        log_bodies = _get("AICM_LOG_BODIES", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        delivery_name = _get("AICM_DELIVERY_TYPE")

        self.logger = create_logger(__name__, log_file, log_level)

        if delivery is not None:
            self.delivery = delivery
            delivery_type = getattr(delivery, "type", None)
        else:
            if delivery_name:
                delivery_type = DeliveryType(delivery_name.lower())
            elif db_path:
                delivery_type = DeliveryType.PERSISTENT_QUEUE
            else:
                delivery_type = DeliveryType.IMMEDIATE
            dconfig = DeliveryConfig(
                ini_manager=self.ini_manager,
                aicm_api_key=self.aicm_api_key,
                aicm_api_base=api_base,
                aicm_api_url=api_url,
                timeout=timeout,
                log_file=log_file,
                log_level=log_level,
                immediate_pause_seconds=immediate_pause_seconds,
            )
            self.delivery = create_delivery(
                delivery_type,
                dconfig,
                db_path=db_path,
                poll_interval=poll_interval,
                batch_interval=batch_interval,
                max_attempts=max_attempts,
                max_retries=max_retries,
                max_batch_size=max_batch_size,
                log_bodies=log_bodies,
            )
        if delivery_type is not None:
            self.ini_manager.set_option(
                "tracker", "AICM_DELIVERY_TYPE", delivery_type.value.upper()
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
    ) -> Any:
        """Track usage data.

        For immediate delivery, returns a dict with ``result`` and
        ``triggered_limits`` keys. For queued delivery, returns a dict
        ``{"queued": <count>}`` indicating the queue length.
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
        result = self.delivery.enqueue(record)
        if isinstance(result, int):
            return {"queued": result, "response_id": record["response_id"]}
        return result

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
    ) -> Any:
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
            track_result = self.track(
                api_id,
                system_key,
                usage,
                response_id=response_id,
                timestamp=timestamp,
                client_customer_key=client_customer_key,
                context=context,
            )
            try:
                setattr(
                    response,
                    "aicm_response_id",
                    track_result.get("result", {}).get("response_id"),
                )
                setattr(response, "aicm_track_result", track_result)
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
        """Release any resources associated with the tracker.

        A ``Tracker`` may be constructed with an explicitly provided delivery
        instance.  Historically such deliveries were treated as externally
        managed and were not stopped when the tracker was closed.  This led to
        surprising behaviour where queued deliveries (like
        :class:`PersistentDelivery`) could continue running after the tracker
        context exited, leaving callers unsure when the queue had fully drained.

        To provide predictable shutdown semantics, ``close()`` now always stops
        the associated delivery instance.  Callers that wish to reuse a single
        delivery across multiple trackers should manage the delivery lifecycle
        separately instead of relying on the tracker's context manager.
        """

        if getattr(self, "delivery", None) is not None:
            self.delivery.stop()
