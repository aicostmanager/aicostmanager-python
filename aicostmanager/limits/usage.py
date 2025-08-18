from __future__ import annotations

from typing import Iterable

from ..client import CostManagerClient
from ..models import UsageLimitIn, UsageLimitOut, UsageLimitProgressOut
from .base import BaseLimitManager


class UsageLimitManager(BaseLimitManager):
    """Manage usage limits via the :class:`CostManagerClient`."""

    def list_usage_limits(self) -> Iterable[UsageLimitOut]:
        return list(self.client.list_usage_limits())

    def create_usage_limit(self, data: UsageLimitIn | dict) -> UsageLimitOut:
        return self.client.create_usage_limit(data)

    def get_usage_limit(self, limit_id: str) -> UsageLimitOut:
        return self.client.get_usage_limit(limit_id)

    def update_usage_limit(self, limit_id: str, data: UsageLimitIn | dict) -> UsageLimitOut:
        return self.client.update_usage_limit(limit_id, data)

    def delete_usage_limit(self, limit_id: str) -> None:
        self.client.delete_usage_limit(limit_id)

    def list_usage_limit_progress(self) -> Iterable[UsageLimitProgressOut]:
        return list(self.client.list_usage_limit_progress())
