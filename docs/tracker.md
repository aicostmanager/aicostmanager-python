# Tracker

The `Tracker` provides a lightweight way to send arbitrary usage payloads to
AICostManager's `/track` endpoint.  It does not require configuration metadata
and forwards any JSON-serialisable data that you supply.

## Creating a tracker

```python
# Uses API key from environment by default and ensures the
# delivery queue is flushed on exit
with Tracker() as tracker:
    ...  # call track() as needed
```

## Choosing a delivery manager

The tracker supports multiple delivery strategies selected via `DeliveryType`. The default `immediate` mode sends each record synchronously with up to three retries for transient errors. Use `mem_queue` for an in-memory background queue or `persistent_queue` for a durable SQLite-backed queue:

```python
from aicostmanager import Tracker, DeliveryType

tracker = Tracker(delivery_type=DeliveryType.MEM_QUEUE)
```

The constructor accepts the same connection options as
`PersistentDelivery`, such as `aicm_api_key`, `aicm_api_base` and
`aicm_ini_path`.  The delivery system writes logs to the Python logging
module.  To inspect activity, pass `log_file` and a verbose
`log_level`:

```python
tracker = Tracker(log_file="/tmp/aicm.log", log_level="DEBUG", log_bodies=True)
```

Logs will contain entries for enqueued items, attempted deliveries and
failures, allowing you to verify behaviour during tests or development.

## Background tracking

`track` builds a record and places it on a durable queue for background
processing:

```python
usage = {"input_tokens": 10, "output_tokens": 20}
tracker.track("openai", "gpt-5-mini", usage)
```

Optional fields let you attach metadata or override identifiers:

```python
tracker.track(
    "openai",
    "gpt-5-mini",
    usage,
    client_customer_key="acme_corp",
    context={"env": "prod"},
    response_id="external-session-id",
    timestamp="2024-01-01T00:00:00Z",
)
```

## Asynchronous usage

All operations are safe to call from asynchronous applications.  The
method `track_async` runs the corresponding synchronous logic in a worker
thread:

```python
await tracker.track_async("openai", "gpt-5-mini", usage)
```

Example FastAPI integration:

```python
from fastapi import FastAPI
from aicostmanager import Tracker

app = FastAPI()
tracker = Tracker()

@app.on_event("shutdown")
def shutdown() -> None:
    tracker.close()

@app.post("/track")
async def track(payload: dict) -> dict:
    await tracker.track_async("openai", "gpt-5-mini", payload)
    return {"status": "queued"}
```

## Shutting down

`Tracker` owns a background worker responsible for delivering queued
messages. Using it as a context manager ensures the queue is flushed and
stopped automatically.  If you create a tracker outside of a `with`
block, call `close()` during application shutdown:

```python
with Tracker() as tracker:
    ...

# or manually
tracker = Tracker()
...  # use tracker
tracker.close()
```

