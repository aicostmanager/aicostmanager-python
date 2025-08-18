from __future__ import annotations
from typing import Any

from ..models import ErrorResponse


class AICMError(Exception):
    """Base exception for SDK errors."""


class MissingConfiguration(AICMError):
    """Raised when required configuration is missing."""


class APIRequestError(AICMError):
    """Raised for non-successful HTTP responses."""

    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.error_response: ErrorResponse | None = None
        self.error: str | None = None
        self.message: str | None = None
        self.details: Any | None = None
        if isinstance(detail, dict):
            try:
                self.error_response = ErrorResponse.model_validate(detail)
                self.error = self.error_response.error
                self.message = self.error_response.message
                self.details = self.error_response.details
            except Exception:
                self.error = detail.get("error")
                self.message = detail.get("message")
        super().__init__(f"API request failed with status {status_code}: {detail}")


class UsageLimitExceeded(AICMError):
    """Raised when a usage limit has been exceeded and blocks API calls."""

    def __init__(self, triggered_limits: list) -> None:
        self.triggered_limits = triggered_limits
        limit_info = ", ".join(
            [f"limit {tl.limit_id} ({tl.threshold_type})" for tl in triggered_limits]
        )
        super().__init__(f"Usage limit exceeded: {limit_info}")
