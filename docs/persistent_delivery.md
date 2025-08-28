# PersistentDelivery

`PersistentDelivery` provides a durable, thread based queue for sending
usage information to the AICostManager `/track` endpoint. Messages are stored
in a local SQLite database using write ahead logging so that they survive
restarts and power loss.  A background worker fetches queued messages,
bundles up to 100 at a time into a single request, and retries delivery with
exponential backoff. The worker flushes whatever has been collected every
`batch_interval` seconds (default `0.5`) so it doesn't wait for a full batch
before sending.

## Configuration

Values can be supplied directly or through environment variables and the
`AICM.INI` file.  The following environment variables are recognised:

- `AICM_API_KEY`
- `AICM_API_BASE` (default: `https://aicostmanager.com`)
- `AICM_API_URL` (default: `/api/v1`)
- `AICM_DB_PATH` (default: `~/.config/aicostmanager/queue.db`)
- `AICM_LOG_FILE` (default: `~/.config/aicostmanager/aicm.log`)
- `AICM_LOG_LEVEL`
- `AICM_LOG_BODIES`
- `AICM_TIMEOUT`
- `AICM_POLL_INTERVAL`
- `AICM_BATCH_INTERVAL`
- `AICM_IMMEDIATE_PAUSE_SECONDS`
- `AICM_MAX_ATTEMPTS`
- `AICM_MAX_RETRIES`
- `AICM_MAX_BATCH_SIZE`

The same options may be placed in a `[tracker]` section inside the INI file.
Standard precedence is:

1. Arguments passed to `PersistentDelivery`
2. `[tracker]` section in `AICM.INI`
3. Environment variables
4. Built-in defaults

## Basic Usage

```python
from aicostmanager import PersistentDelivery

payload = {"api_id": "openai", "service_key": "gpt", "payload": {"tokens": 1}}

# Simple initialization with defaults
# - API key from AICM_API_KEY environment variable
# - Database path: ~/.cache/aicostmanager/delivery_queue.db
# - Standard configuration defaults
delivery = PersistentDelivery()
delivery.enqueue(payload)             # queue for background delivery
```

### Custom Configuration

You can override defaults as needed:

```python
# Custom database path
delivery = PersistentDelivery(db_path="/custom/path/queue.db")

# Custom batch interval and other settings
delivery = PersistentDelivery(
    batch_interval=1.0,
    max_batch_size=500
)

# Full custom configuration
from aicostmanager import DeliveryConfig
from aicostmanager.ini_manager import IniManager

config = DeliveryConfig(
    ini_manager=IniManager(IniManager.resolve_path(None)),
    aicm_api_key="sk-custom-key",
    aicm_api_base="https://custom.endpoint.com"
)
delivery = PersistentDelivery(config=config, db_path="/custom/queue.db")
```

The queue can be inspected for runtime statistics:

```python
stats = delivery.stats()
print(stats)
```

Call `stop()` to flush and close resources when shutting down.
```
delivery.stop()
```

For troubleshooting, full request and response bodies can be logged (with
common sensitive fields redacted) by passing `log_bodies=True` when creating
`PersistentDelivery` or setting the environment variable
`AICM_LOG_BODIES`.

See [PersistentDelivery Logging](persistent_delivery_logging.md) for a detailed guide to log configuration and troubleshooting.

## Maintenance

Use `PersistentQueueManager` to inspect queue statistics, examine failures, or
requeue problematic items:

```python
from aicostmanager.delivery import PersistentQueueManager

mgr = PersistentQueueManager("/path/to/queue.db")
print(mgr.stats())
```

`PersistentDelivery` logs a warning on startup if failed items are present and
refers to this tool for remediation.

For real-time monitoring during development, the package includes a small
`queue-monitor` CLI that continuously prints queue statistics and recent
failures:

```
uv run queue-monitor /path/to/queue.db
```
