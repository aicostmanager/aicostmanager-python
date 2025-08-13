# Tracker

The `Tracker` provides a lightweight way to send arbitrary usage payloads to
AICostManager's `/track` endpoint.  It does not require configuration metadata
and forwards any JSON-serialisable data that you supply.

## Creating a tracker

```python
from aicostmanager import Tracker

# Uses API key from environment by default
tracker = Tracker()
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

## Immediate delivery

Use `deliver_now` to bypass the queue and synchronously send a record.
The method returns the `httpx.Response` from the server so tests can
assert on the result:

```python
resp = tracker.deliver_now("openai", "gpt-5-mini", usage)
assert resp.status_code == 200
```

Alias methods `sync_track` and `track_sync` are provided for backwards
compatibility and behave identically to `deliver_now`.

## Asynchronous usage

All operations are safe to call from asynchronous applications.  The
methods `track_async` and `deliver_now_async` run the corresponding
synchronous logic in a worker thread:

```python
await tracker.track_async("openai", "gpt-5-mini", usage)
response = await tracker.deliver_now_async("openai", "gpt-5-mini", usage)
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
messages.  Call `close()` during application shutdown to flush the queue
and stop the worker:

```python
tracker.close()
```

