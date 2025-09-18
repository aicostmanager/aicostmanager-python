from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
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
        delivery_type: DeliveryType | str | None = None,
    ) -> None:
        self.ini_manager = IniManager(IniManager.resolve_path(ini_path))
        self.ini_path = self.ini_manager.ini_path
        self.aicm_api_key = aicm_api_key or os.getenv("AICM_API_KEY")
        ini_dir = Path(self.ini_path).resolve().parent

        def _get(option: str, default: str | None = None) -> str | None:
            val = self.ini_manager.get_option("tracker", option)
            if val is not None:
                return val
            return os.getenv(option, default)

        api_base = _get("AICM_API_BASE", "https://aicostmanager.com")
        api_url = _get("AICM_API_URL", "/api/v1")
        log_file = _get("AICM_LOG_FILE", str(ini_dir / "aicm.log"))
        log_level = _get("AICM_LOG_LEVEL")
        timeout = float(_get("AICM_TIMEOUT", "10.0"))
        poll_interval = float(_get("AICM_POLL_INTERVAL", "0.1"))
        batch_interval = float(_get("AICM_BATCH_INTERVAL", "0.5"))
        immediate_pause_seconds = float(_get("AICM_IMMEDIATE_PAUSE_SECONDS", "5.0"))
        max_attempts = int(_get("AICM_MAX_ATTEMPTS", "3"))
        max_retries = int(_get("AICM_MAX_RETRIES", "5"))
        max_batch_size = int(_get("AICM_MAX_BATCH_SIZE", "1000"))
        log_bodies_val = _get("AICM_LOG_BODIES", "false")
        log_bodies = str(log_bodies_val).lower() in {"1", "true", "yes", "on"}

        raise_on_error_val = _get("AICM_RAISE_ON_ERROR", "false")
        raise_on_error = str(raise_on_error_val).lower() in {"1", "true", "yes", "on"}

        db_path = _get("AICM_DB_PATH", str(ini_dir / "queue.db"))
        delivery_name_cfg = _get("AICM_DELIVERY_TYPE")

        self.logger = create_logger(__name__, log_file, log_level)

        if delivery is not None:
            self.delivery = delivery
            resolved_type = getattr(delivery, "type", None)
        else:
            delivery_name_arg = (
                delivery_type.value
                if isinstance(delivery_type, DeliveryType)
                else delivery_type
            )
            if delivery_name_arg is not None:
                resolved_type = DeliveryType(str(delivery_name_arg).lower())
            elif delivery_name_cfg:
                resolved_type = DeliveryType(delivery_name_cfg.lower())
            else:
                resolved_type = DeliveryType.IMMEDIATE

            final_db_path = (
                db_path if resolved_type == DeliveryType.PERSISTENT_QUEUE else None
            )

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
                resolved_type,
                dconfig,
                db_path=final_db_path,
                poll_interval=poll_interval,
                batch_interval=batch_interval,
                max_attempts=max_attempts,
                max_retries=max_retries,
                max_batch_size=max_batch_size,
                log_bodies=log_bodies,
                raise_on_error=raise_on_error,
            )
        if resolved_type is not None:
            self.ini_manager.set_option(
                "tracker", "AICM_DELIVERY_TYPE", resolved_type.value.upper()
            )

        # Instance-level tracking metadata
        self.customer_key: Optional[str] = None
        self.context: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Configuration Methods
    # ------------------------------------------------------------------
    def set_customer_key(self, key: str | None) -> None:
        """Update the ``customer_key`` used for tracking."""
        self.customer_key = key

    def set_context(self, context: Dict[str, Any] | None) -> None:
        """Update the ``context`` dictionary used for tracking."""
        self.context = context

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------
    def _get_vendor_api_mapping(self, service_key: str) -> Tuple[str, str]:
        """Extract vendor and api_id from service_key.

        Returns:
            Tuple of (vendor, api_id)
        """
        if "::" in service_key:
            vendor = service_key.split("::")[0]
            # Map vendor to api_id
            vendor_to_api = {
                "openai": "openai_chat",
                "anthropic": "anthropic",
                "amazon-bedrock": "amazon-bedrock",
                "fireworks-ai": "openai_chat",  # Fireworks uses OpenAI-compatible API
                "xai": "openai_chat",  # X.AI uses OpenAI-compatible API
                "google": "gemini",
            }
            api_id = vendor_to_api.get(vendor, vendor)
            return vendor, api_id
        else:
            # If no "::" found, assume it's already an api_id
            return service_key, service_key

    def _build_final_service_key(
        self, service_key: str, api_id: str, response_or_chunk: Any
    ) -> str:
        """Build the final service_key from api_id and model if needed."""
        if "::" not in service_key:
            # service_key was actually an api_id, extract model from response
            model = getattr(response_or_chunk, "model", None)
            if model:
                # Map api_id back to vendor
                api_to_vendor = {
                    "openai_chat": "openai",
                    "openai_responses": "openai",
                    "anthropic": "anthropic",
                    "amazon-bedrock": "amazon-bedrock",
                    "gemini": "google",
                }
                vendor = api_to_vendor.get(api_id, api_id)
                return f"{vendor}::{model}"
        return service_key

    def _resolve_tracking_params(
        self, customer_key: Optional[str], context: Optional[Dict[str, Any]]
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Resolve tracking parameters using instance defaults as fallbacks."""
        resolved_key = customer_key if customer_key is not None else self.customer_key
        resolved_context = context if context is not None else self.context
        return resolved_key, resolved_context

    def _build_record(
        self,
        service_key: str,
        usage: Dict[str, Any],
        *,
        response_id: Optional[str],
        timestamp: str | datetime | None,
        customer_key: Optional[str],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "service_key": service_key,
            "response_id": response_id or uuid4().hex,
            "timestamp": (
                str(timestamp.timestamp())
                if isinstance(timestamp, datetime)
                else str(datetime.fromisoformat(timestamp).timestamp())
                if isinstance(timestamp, str)
                else str(datetime.now(timezone.utc).timestamp())
            ),
            "payload": usage,
        }
        if customer_key is not None:
            record["customer_key"] = customer_key
        if context is not None:
            record["context"] = context
        return record

    # ------------------------------------------------------------------
    # Core Tracking Methods
    # ------------------------------------------------------------------
    def track(
        self,
        service_key: str,
        usage: Dict[str, Any],
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Track usage data.

        For immediate delivery, returns a dict with ``result`` and
        ``triggered_limits`` keys. For queued delivery, returns a dict
        ``{"queued": <count>}`` indicating the queue length.
        """
        # Use instance-level values as fallbacks if parameters are None
        customer_key, context = self._resolve_tracking_params(customer_key, context)

        record = self._build_record(
            service_key,
            usage,
            response_id=response_id,
            timestamp=timestamp,
            customer_key=customer_key,
            context=context,
        )
        result = self.delivery.enqueue(record)
        if isinstance(result, int):
            return {"queued": result, "response_id": record["response_id"]}
        return result

    async def track_async(
        self,
        service_key: str,
        usage: Dict[str, Any],
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        return await asyncio.to_thread(
            self.track,
            service_key,
            usage,
            response_id=response_id,
            timestamp=timestamp,
            customer_key=customer_key,
            context=context,
        )

    # ------------------------------------------------------------------
    # LLM Tracking Methods
    # ------------------------------------------------------------------
    def track_llm_usage(
        self,
        service_key: str,
        response: Any,
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Extract usage from an LLM response and enqueue it.

        Parameters are identical to :meth:`track` except that ``response`` is
        the raw LLM client response.  Usage information is obtained via
        :func:`get_usage_from_response` using the provided ``service_key``.
        ``response`` is returned to allow call chaining. If a ``response_id`` was
        not provided and one is generated, it is attached to the response as
        ``response.aicm_response_id`` for convenience.
        """
        vendor, api_id = self._get_vendor_api_mapping(service_key)

        usage = get_usage_from_response(response, api_id)
        if isinstance(usage, dict) and usage:
            final_service_key = self._build_final_service_key(
                service_key, api_id, response
            )

            track_result = self.track(
                final_service_key,
                usage,
                response_id=response_id,
                timestamp=timestamp,
                customer_key=customer_key,
                context=context,
            )
            self._attach_tracking_metadata(response, track_result)
        return response

    def _attach_tracking_metadata(self, response: Any, track_result: Any) -> None:
        """Safely attach tracking metadata to response object."""
        try:
            setattr(
                response,
                "aicm_response_id",
                track_result.get("result", {}).get("response_id"),
            )
            setattr(response, "aicm_track_result", track_result)
        except Exception:
            pass

    async def track_llm_usage_async(
        self,
        service_key: str,
        response: Any,
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Async version of :meth:`track_llm_usage`."""
        return await asyncio.to_thread(
            self.track_llm_usage,
            service_key,
            response,
            response_id=response_id,
            timestamp=timestamp,
            customer_key=customer_key,
            context=context,
        )

    def track_llm_stream_usage(
        self,
        service_key: str,
        stream: Any,
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Yield streaming events while tracking usage.

        ``stream`` should be an iterable of events from an LLM SDK.  Usage
        information is extracted from events using
        :func:`get_streaming_usage_from_response` and sent via :meth:`track` once
        available.
        """
        vendor, api_id = self._get_vendor_api_mapping(service_key)

        usage_sent = False
        for chunk in stream:
            if not usage_sent:
                usage = get_streaming_usage_from_response(chunk, api_id)
                if isinstance(usage, dict) and usage:
                    # For streaming, try to get model from both stream and chunk
                    chunk_with_model = type(
                        "MockResponse",
                        (),
                        {
                            "model": getattr(stream, "model", None)
                            or getattr(chunk, "model", None)
                        },
                    )()
                    final_service_key = self._build_final_service_key(
                        service_key, api_id, chunk_with_model
                    )

                    self.track(
                        final_service_key,
                        usage,
                        response_id=response_id,
                        timestamp=timestamp,
                        customer_key=customer_key,
                        context=context,
                    )
                    usage_sent = True
            yield chunk

    async def track_llm_stream_usage_async(
        self,
        service_key: str,
        stream: Any,
        *,
        response_id: Optional[str] = None,
        timestamp: str | datetime | None = None,
        customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Asynchronous version of :meth:`track_llm_stream_usage`."""
        vendor, api_id = self._get_vendor_api_mapping(service_key)

        usage_sent = False
        async for chunk in stream:
            if not usage_sent:
                usage = get_streaming_usage_from_response(chunk, api_id)
                if isinstance(usage, dict) and usage:
                    # For streaming, try to get model from both stream and chunk
                    chunk_with_model = type(
                        "MockResponse",
                        (),
                        {
                            "model": getattr(stream, "model", None)
                            or getattr(chunk, "model", None)
                        },
                    )()
                    final_service_key = self._build_final_service_key(
                        service_key, api_id, chunk_with_model
                    )

                    await self.track_async(
                        final_service_key,
                        usage,
                        response_id=response_id,
                        timestamp=timestamp,
                        customer_key=customer_key,
                        context=context,
                    )
                    usage_sent = True
            yield chunk

    # ------------------------------------------------------------------
    # Context Manager and Lifecycle Methods
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
