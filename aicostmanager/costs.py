from __future__ import annotations

from typing import Any, Dict, Iterator, Optional

from .client import CostManagerClient
from .models import CostEventFilters, CostEventItem, CostEventsResponse


class CostQueryManager:
    """Helper class for querying cost events from the API."""

    def __init__(
        self,
        client: Optional[CostManagerClient] = None,
        **client_kwargs: Any,
    ) -> None:
        """Create a :class:`CostQueryManager`.

        Parameters
        ----------
        client:
            Optional pre-configured :class:`~aicostmanager.client.CostManagerClient`.
            If not provided, one will be created using ``client_kwargs``.
        client_kwargs:
            Keyword arguments forwarded to :class:`CostManagerClient` when ``client``
            is not provided.
        """

        self.client = client or CostManagerClient(**client_kwargs)

    def close(self) -> None:
        """Close the underlying :class:`CostManagerClient` session."""

        self.client.close()

    def __enter__(self) -> "CostQueryManager":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def list_costs(
        self,
        filters: CostEventFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        """Return raw cost event data from the ``/costs`` endpoint."""

        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        return self.client._request("GET", "/costs/", params=params)

    def list_costs_typed(
        self,
        filters: CostEventFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> CostEventsResponse:
        """Typed variant of :meth:`list_costs`."""

        data = self.list_costs(filters, **params)
        return CostEventsResponse.model_validate(data)

    def iter_costs(
        self,
        filters: CostEventFilters | Dict[str, Any] | None = None,
        **params: Any,
    ) -> Iterator[CostEventItem]:
        """Iterate over cost events across paginated responses."""

        if filters:
            if hasattr(filters, "model_dump"):
                params.update(filters.model_dump(exclude_none=True))
            else:
                params.update({k: v for k, v in filters.items() if v is not None})
        for item in self.client._iter_paginated("/costs/", **params):
            yield CostEventItem.model_validate(item)
