"""Backward compatibility shim for ClientCostManager."""

from .wrappers.client import ClientCostManager, NestedAttributeWrapper, _StreamIterator

CostManager = ClientCostManager

__all__ = ["CostManager", "NestedAttributeWrapper", "_StreamIterator"]
