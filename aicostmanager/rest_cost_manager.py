"""Backward compatibility shim for REST wrappers."""

from .wrappers.rest import RestUsageWrapper, AsyncRestUsageWrapper

RestCostManager = RestUsageWrapper
AsyncRestCostManager = AsyncRestUsageWrapper

__all__ = ["RestCostManager", "AsyncRestCostManager"]
