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
        self._retry_queue: queue.Queue[QueueItem] = queue.Queue()
        max_attempts = kwargs.pop("max_attempts", kwargs.pop("max_retries", 5))
        # Enable retries for MemQueue to match PersistentDelivery behavior
        super().__init__(
            config, max_attempts=max_attempts, max_retries=max_attempts, **kwargs
        )

    def _enqueue(self, payload: Dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            self.logger.warning("Delivery queue full")
            self._total_failed += 1

    def get_batch(self, max_batch_size: int, *, block: bool = True) -> List[QueueItem]:
        batch: List[QueueItem] = []

        # First, check for retry items that are ready to be processed
        retry_items = []
        current_time = time.time()
        try:
            while len(retry_items) < max_batch_size:
                item = self._retry_queue.get_nowait()
                if hasattr(item, "scheduled_at") and item.scheduled_at <= current_time:
                    retry_items.append(item)
                elif hasattr(item, "scheduled_at"):
                    # Put it back, not ready yet
                    self._retry_queue.put_nowait(item)
                    break
                else:
                    # No scheduled_at, process immediately
                    retry_items.append(item)
        except queue.Empty:
            pass

        batch.extend(retry_items)

        # Then get new items from the main queue
        if len(batch) < max_batch_size:
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

    def reschedule(self, item: QueueItem) -> None:
        """Reschedule a failed item for retry."""
        if item.retry_count >= self.max_retries:
            # Max retries exceeded, drop the item
            return

        # Schedule for retry with exponential backoff
        retry_delay = min(2**item.retry_count, 300)  # Cap at 5 minutes
        item.scheduled_at = time.time() + retry_delay

        try:
            self._retry_queue.put_nowait(item)
        except queue.Full:
            self.logger.warning("Retry queue full, dropping item")

    def acknowledge(self, items: List[QueueItem]) -> None:
        """Acknowledge successful delivery of items."""
        # For MemQueue, acknowledgment is implicit (items are removed from queue)
        pass

    def queued(self) -> int:
        return self._queue.qsize() + self._retry_queue.qsize()
