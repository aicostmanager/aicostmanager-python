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

Configuration values are read from an ``AICM.INI`` file.

### Configuration resolution order

Tracker settings can come from several places. When a value is defined in
multiple locations, the resolution order is:

1. Arguments passed directly to :class:`Tracker` or a delivery class
2. Environment variables (``AICM_*``)
3. Values in ``AICM.INI``
4. Built-in defaults

For example, an environment variable can override a value stored in the INI
file:

```ini
# AICM.INI
[tracker]
AICM_TIMEOUT=10.0
```

```bash
export AICM_TIMEOUT=5.0
```

```python
from aicostmanager import Tracker
tracker = Tracker()  # Uses a 5 second timeout
```

See [`config.md`](config.md) for the full list of settings.

## Choosing a delivery manager

The tracker supports multiple delivery strategies. The default ``IMMEDIATE`` mode sends each record
synchronously with up to three retries for transient errors. By default, failures to reach the
tracking API are logged and ignored; set ``AICM_RAISE_ON_ERROR=true`` to raise exceptions instead. Use
``PERSISTENT_QUEUE`` for a durable SQLite-backed queue with background
delivery.

### Method 1: Constructor argument (highest precedence)
```python
tracker = Tracker(delivery_type="PERSISTENT_QUEUE")
```

### Method 2: Environment variable (simplest)
```python
import os
os.environ['AICM_DELIVERY_TYPE'] = 'PERSISTENT_QUEUE'
tracker = Tracker()
```

### Method 3: Direct delivery instance (recommended for web apps)
```python
from aicostmanager import PersistentDelivery
# Simple initialization with intelligent defaults
persistent_delivery = PersistentDelivery()
tracker = Tracker(delivery=persistent_delivery)
```

### Method 4: INI file configuration
Set ``AICM_DELIVERY_TYPE`` in ``AICM.INI``:
```ini
[tracker]
AICM_DELIVERY_TYPE=PERSISTENT_QUEUE
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
successfully sending a batch. Triggered limits are matched by API key ID and
optionally by ``client_customer_key`` and ``service_key``. The service key is
treated as an opaque value and is **not** split into vendor and service
components. The decrypted limits are cached in memory and persisted to
``AICM.ini`` as a fallback. Enqueued payloads are compared against this
in-memory cache and
:class:`~aicostmanager.client.exceptions.UsageLimitExceeded` is raised if the
payload matches a triggered limit. The check occurs *after* the enqueue or
delivery action so tracking data is never discarded even when a limit has been
reached.

## Asynchronous usage

All operations are safe to call from asynchronous applications.  The
method `track_async` runs the corresponding synchronous logic in a worker
thread:

```python
await tracker.track_async("openai", "gpt-5-mini", usage)
```

Example FastAPI integration:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from aicostmanager import Tracker, PersistentDelivery

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - use persistent delivery for reliability
    persistent_delivery = PersistentDelivery()
    app.state.tracker = Tracker(delivery=persistent_delivery)
    yield
    # Shutdown
    app.state.tracker.close()

app = FastAPI(lifespan=lifespan)

@app.post("/track")
async def track(payload: dict) -> dict:
    await app.state.tracker.track_async("openai", "gpt-5-mini", payload)
    return {"status": "queued"}
```

## LLM response helpers

The tracker can derive token usage directly from OpenAI responses. Using the
tracker as a context manager guarantees the usage is flushed before your
program exits. If you prefer automatic tracking without calling these helper
methods, see the [LLM wrappers](llm_wrappers.md) which proxy common SDK clients
and record usage for you.

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

