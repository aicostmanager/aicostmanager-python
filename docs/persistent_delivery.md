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
- `AICM_DELIVERY_DB_PATH`
- `AICM_DELIVERY_LOG_FILE`
- `AICM_DELIVERY_LOG_LEVEL`

The same options may be placed in a `[delivery]` section inside the INI file.

## Basic Usage

```python
from aicostmanager import PersistentDelivery

payload = {"api_id": "openai", "service_key": "gpt", "payload": {"tokens": 1}}

delivery = PersistentDelivery(aicm_api_key="sk-test", batch_interval=0.5)
delivery.enqueue(payload)             # queued for background delivery
delivery.deliver_now(payload)         # immediate delivery of a single record
```

The queue can be inspected for health information:

```python
stats = delivery.health()
print(stats)
```

Call `stop()` to flush and close resources when shutting down.
```
delivery.stop()
```
