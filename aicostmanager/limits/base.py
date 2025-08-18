from __future__ import annotations

from ..client import CostManagerClient


class BaseLimitManager:
    """Common base class for limit managers."""

    def __init__(self, client: CostManagerClient) -> None:
        self.client = client
