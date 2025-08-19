# Tracker

The `Tracker` provides a lightweight way to send arbitrary usage payloads to
AICostManager's `/track` endpoint.  It does not require configuration metadata
and forwards any JSON-serialisable data that you supply.

Before using the tracker, create a free account at
[AICostManager](https://aicostmanager.com) and set your API key in the
`AICM_API_KEY` environment variable or pass it to the constructor.

## Creating a tracker

```python
# Uses API key from environment by default and ensures the
# delivery queue is flushed on exit
with Tracker() as tracker:
    ...  # call track() as needed
```

For explicit control over configuration, build a ``TrackerConfig`` from the
environment and INI file:

```python
from aicostmanager import Tracker, TrackerConfig

config = TrackerConfig.from_env()
tracker = Tracker(config)
```

## Choosing a delivery manager

The tracker supports multiple delivery strategies selected via `DeliveryType`. The default `immediate` mode sends each record synchronously with up to three retries for transient errors. Use `mem_queue` for an in-memory background queue or `persistent_queue` for a durable SQLite-backed queue:

```python
from aicostmanager import Tracker, DeliveryType

tracker = Tracker(delivery_type=DeliveryType.MEM_QUEUE)
```

``TrackerConfig.from_env`` accepts the same connection options as
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

### Triggered limit enforcement

Every delivery mechanism refreshes triggered limit data from the API after
successfully sending a batch. Once a payload is enqueued, the tracker compares
it against the cached limits and raises
:class:`~aicostmanager.client.exceptions.UsageLimitExceeded` if the payload
matches a triggered limit. The check occurs *after* the enqueue or delivery
action so tracking data is never discarded even when a limit has been reached.

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

## LLM response helpers

The tracker can derive token usage directly from OpenAI responses. Using the
tracker as a context manager guarantees the usage is flushed before your
program exits.

### Non-streaming example

```python
from aicostmanager import Tracker
from openai import OpenAI

client = OpenAI()

with Tracker() as tracker:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Give me a haiku about snow."}],
    )
    tracker.track_llm_usage("openai_chat", resp)
    print(resp.choices[0].message.content)
```

1. `OpenAI()` constructs the API client.
2. `with Tracker() as tracker:` sets up cost tracking and ensures the queue is
   flushed.
3. A chat completion call is made.
4. `track_llm_usage` extracts token usage from the response and sends it to
   AICostManager.
5. Exiting the `with` block delivers the queued usage.

### Streaming example

```python
from aicostmanager import Tracker
from openai import OpenAI

client = OpenAI()

with Tracker() as tracker:
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Stream a short poem."}],
        stream=True,
        stream_options={"include_usage": True},
    )

    for event in tracker.track_llm_stream_usage("openai_chat", stream):
        if event.type == "message.delta" and event.delta.get("content"):
            print(event.delta["content"], end="")
    print()
```

1. `stream=True` returns an iterator of events instead of a full response.
2. `track_llm_stream_usage` wraps the iterator so the tracker can record usage
   once the stream completes.
3. `include_usage` must be set so the final event contains the token counts.
4. The loop handles each incoming delta while the tracker captures usage behind
   the scenes.

Asynchronous variants ``track_llm_usage_async`` and
``track_llm_stream_usage_async`` mirror the synchronous versions.

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

