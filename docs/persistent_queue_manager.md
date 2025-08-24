# Persistent Queue Manager

`PersistentQueueManager` provides tools for inspecting and maintaining the
SQLite queue used by `PersistentDelivery`.

```python
from aicostmanager.delivery import PersistentQueueManager

manager = PersistentQueueManager("/path/to/queue.db")
```

## Statistics

```python
manager.stats()
# {'queued': 10, 'failed': 2}
```

## Inspect failed items

```python
for item in manager.list_failed():
    print(item["id"], item["payload"])
```

## Requeue or purge failures

```python
manager.requeue_failed()        # retry all failed items
manager.purge_failed([1, 2])    # delete specific failures
```

See the warning emitted by `PersistentDelivery` on startup for guidance when
failed items are detected.
