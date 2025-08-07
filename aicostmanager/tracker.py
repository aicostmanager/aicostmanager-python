from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import asyncio
from uuid import uuid4

from .client import CostManagerClient
from .config_manager import Config, CostManagerConfig
from .delivery import ResilientDelivery, get_global_delivery
from .type_validator import TypeValidator


class UsageValidationError(ValueError):
    """Raised when supplied usage data fails schema validation."""

    def __init__(
        self,
        errors: Dict[str, str] | None = None,
        missing_fields: list[str] | None = None,
        extra_fields: list[str] | None = None,
    ) -> None:
        errors = errors or {}
        missing_fields = missing_fields or []
        extra_fields = extra_fields or []
        messages = []
        if missing_fields:
            messages.append(f"Missing fields: {', '.join(missing_fields)}")
        if errors:
            messages.append(
                "Type errors: "
                + "; ".join(f"{field}: {msg}" for field, msg in errors.items())
            )
        if extra_fields:
            messages.append(f"Unexpected fields: {', '.join(extra_fields)}")
        super().__init__("; ".join(messages))
        self.errors = errors
        self.missing_fields = missing_fields
        self.extra_fields = extra_fields


class Tracker:
    """Manually track usage for a given configuration and service."""

    def __init__(
        self,
        config_id: str,
        service_id: str,
        *,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        aicm_ini_path: Optional[str] = None,
        delivery: ResilientDelivery | None = None,
        delivery_queue_size: int = 1000,
        delivery_max_retries: int = 5,
        delivery_timeout: float = 10.0,
        delivery_batch_interval: float | None = None,
        delivery_max_batch_size: int = 100,
        delivery_mode: str | None = None,
        delivery_on_full: str = "backpressure",
    ) -> None:
        self.config_id = config_id
        self.service_id = service_id
        self.cm_client = CostManagerClient(
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
        )
        self.config_manager = CostManagerConfig(self.cm_client)
        cfg: Config = self.config_manager.get_config_by_id(config_id)
        self.manual_usage_schema: Dict[str, str] = cfg.manual_usage_schema or {}
        self._validator = TypeValidator()
        if delivery is not None:
            self.delivery = delivery
        else:
            self.delivery = get_global_delivery(
                self.cm_client,
                max_retries=delivery_max_retries,
                queue_size=delivery_queue_size,
                timeout=delivery_timeout,
                batch_interval=delivery_batch_interval,
                max_batch_size=delivery_max_batch_size,
                delivery_mode=delivery_mode,
                on_full=delivery_on_full,
            )

    @classmethod
    async def create_async(
        cls,
        config_id: str,
        service_id: str,
        *,
        aicm_api_key: Optional[str] = None,
        aicm_api_base: Optional[str] = None,
        aicm_api_url: Optional[str] = None,
        aicm_ini_path: Optional[str] = None,
        delivery: ResilientDelivery | None = None,
        delivery_queue_size: int = 1000,
        delivery_max_retries: int = 5,
        delivery_timeout: float = 10.0,
        delivery_batch_interval: float | None = None,
        delivery_max_batch_size: int = 100,
        delivery_mode: str | None = None,
        delivery_on_full: str = "backpressure",
    ) -> "Tracker":
        """Asynchronously create a fully initialized :class:`Tracker`.

        Configuration loading uses blocking I/O. This factory runs the
        standard constructor in a thread so callers can ``await`` the
        result without blocking the event loop.
        """

        return await asyncio.to_thread(
            cls,
            config_id,
            service_id,
            aicm_api_key=aicm_api_key,
            aicm_api_base=aicm_api_base,
            aicm_api_url=aicm_api_url,
            aicm_ini_path=aicm_ini_path,
            delivery=delivery,
            delivery_queue_size=delivery_queue_size,
            delivery_max_retries=delivery_max_retries,
            delivery_timeout=delivery_timeout,
            delivery_batch_interval=delivery_batch_interval,
            delivery_max_batch_size=delivery_max_batch_size,
            delivery_mode=delivery_mode,
            delivery_on_full=delivery_on_full,
        )

    def track(
        self,
        usage: Dict[str, Any],
        *,
        client_customer_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Validate and deliver a usage record."""
        if self.manual_usage_schema:
            errors: Dict[str, str] = {}
            missing: list[str] = []
            for field, type_str in self.manual_usage_schema.items():
                if field not in usage:
                    if "Optional" not in type_str:
                        missing.append(field)
                    continue
                is_valid, err = self._validator.validate_value(usage[field], type_str)
                if not is_valid:
                    errors[field] = err
            extra = [f for f in usage if f not in self.manual_usage_schema]
            if errors or missing or extra:
                raise UsageValidationError(errors, missing, extra)

        record: Dict[str, Any] = {
            "config_id": self.config_id,
            "service_id": self.service_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "response_id": uuid4().hex,
            "usage": usage,
        }
        if client_customer_key is not None:
            record["client_customer_key"] = client_customer_key
        if context is not None:
            record["context"] = context

        self.delivery.deliver({"usage_records": [record]})
