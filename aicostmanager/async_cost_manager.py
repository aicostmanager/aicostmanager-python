"""Backward compatibility shim for AsyncClientCostManager."""

from .wrappers.client import (
    AsyncClientCostManager,
    AsyncResilientDelivery,
    AsyncNestedAttributeWrapper,
    _AsyncStreamIterator,
)

AsyncCostManager = AsyncClientCostManager

__all__ = [
    "AsyncCostManager",
    "AsyncResilientDelivery",
    "AsyncNestedAttributeWrapper",
    "_AsyncStreamIterator",
]
