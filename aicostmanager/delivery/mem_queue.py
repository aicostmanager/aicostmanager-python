from __future__ import annotations

import queue
import time
from typing import Any, Dict, List

from .base import DeliveryConfig, DeliveryType, QueueDelivery, QueueItem


class MemQueueDelivery(QueueDelivery):
    """In-memory queue with background delivery."""

    type = DeliveryType.MEM_QUEUE

    def __init__(
        self,
        config: DeliveryConfig,
        *,
        queue_size: int = 10000,
        **kwargs: Any,
    ) -> None:
        # Ensure queue is initialized BEFORE the background thread starts in the base class
        self._queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=queue_size)
        max_attempts = kwargs.pop("max_attempts", kwargs.pop("max_retries", 5))
        super().__init__(config, max_attempts=max_attempts, max_retries=0, **kwargs)

    def _enqueue(self, payload: Dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            self.logger.warning("Delivery queue full")
            self._total_failed += 1

    def get_batch(self, max_batch_size: int, *, block: bool = True) -> List[QueueItem]:
        batch: List[QueueItem] = []
        if block:
            deadline = time.time() + self.batch_interval
            while len(batch) < max_batch_size:
                timeout = max(0, deadline - time.time())
                try:
                    payload = self._queue.get(timeout=timeout)
                except queue.Empty:
                    break
                batch.append(QueueItem(payload=payload))
        else:
            while len(batch) < max_batch_size:
                try:
                    payload = self._queue.get_nowait()
                except queue.Empty:
                    break
                batch.append(QueueItem(payload=payload))
        return batch

    def queued(self) -> int:
        return self._queue.qsize()
