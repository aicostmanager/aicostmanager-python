# AICostManager Python SDK

The AICostManager SDK reports AI usage to [AICostManager](https://aicostmanager.com),
helping you track costs across providers.

## Prerequisites

1. Create a **free** account at [aicostmanager.com](https://aicostmanager.com) and
   generate an API key.
2. Export the key as `AICM_API_KEY` or pass it directly to the client or
   tracker.

## Installation

### uv (recommended)

```bash
uv pip install aicostmanager
# or add to an existing project
uv add aicostmanager
```

### pip (fallback)

```bash
pip install aicostmanager
```

## Quick start

### Identify the API and service

Every usage event is tied to two identifiers:

- **api_id** – the API being called (for example, the OpenAI Chat API)
- **service_key** – the specific model or service within that API

1. Visit the [service lookup page](https://aicostmanager.com/services/lookup/) and
   open the **APIs** tab. Copy the `api_id` for the API you are using, e.g.
   `openai_chat`.
2. Switch to the **Services** tab on the same page and copy the full
   `service_key` for your model, e.g. `openai::gpt-5-mini`.

### Track usage

```python
from aicostmanager import Tracker

api_id = "openai_chat"          # copied from the APIs tab
service_key = "openai::gpt-5-mini"  # copied from the Services tab

with Tracker() as tracker:
    tracker.track(api_id, service_key, {
        "input_tokens": 10,
        "output_tokens": 20,
    })
```

Using `with Tracker()` ensures the background delivery queue is flushed before
the program exits.

Configuration values are read from an ``AICM.INI`` file.  See
[`config.md`](docs/config.md) for the complete list of available settings and
their defaults.

## LLM wrappers

Wrap popular LLM SDK clients to record usage automatically without calling
`track` manually:

```python
from aicostmanager import OpenAIChatWrapper
from openai import OpenAI

client = OpenAI()
wrapper = OpenAIChatWrapper(client)

resp = wrapper.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hello"}],
)
print(resp.choices[0].message.content)


wrapper.close()  # optional for immediate delivery; required for queued delivery
```

See [LLM wrappers](docs/llm_wrappers.md) for the full list of supported
providers and advanced usage.

## Choosing a delivery strategy

`Tracker` supports multiple delivery components via `DeliveryType`:

- **Immediate** – send each record synchronously. Ideal for simple scripts or
  tests.
- **Persistent queue** (`DeliveryType.PERSISTENT_QUEUE`) – durable SQLite-backed
  queue for reliability across restarts.

Use the persistent queue for long-running services where losing usage data is
unacceptable and immediate delivery when every call can block on the API. See
[Persistent Delivery](docs/persistent_delivery.md) and the
[Tracker guide](docs/tracker.md#choosing-a-delivery-manager) for details.

## Interpreting `/track` responses

The `/track` endpoint now distinguishes between ingestion and background
processing. Immediate delivery still returns the first result item, but the
payload may not include `cost_events` right away. Instead, check the
`status` field to understand how the event will be processed:

| Status | Meaning |
| ------ | ------- |
| `queued` | The service key is recognised and the event has been queued for processing. |
| `completed` | Processing finished synchronously (legacy servers may still return cost events immediately). |
| `error` | The event failed processing and includes descriptive errors. |
| `service_key_unknown` | The service key is not recognised; the event is quarantined for review. |

Unknown services now produce a friendly error message, for example:

```json
{
  "response_id": "resp-456",
  "status": "service_key_unknown",
  "errors": [
    "Service key 'unknown::service' is not recognized. Event queued for review."
  ]
}
```

Existing integrations should branch on `result.status` and treat
`service_key_unknown` differently from `error`. See the
[tracker documentation](docs/tracker.md#interpreting-results) for detailed
guidance and migration tips.

For real-time insight into the persistent queue, run the `queue-monitor`
command against the SQLite database created by `PersistentDelivery`:

```
uv run queue-monitor ~/.cache/aicostmanager/delivery_queue.db
```

## Tracking in different environments

### Python scripts

Use the context manager shown above to automatically flush the queue.

### Django

```python
# myapp/apps.py
from django.apps import AppConfig
from aicostmanager import Tracker

tracker = Tracker()

class MyAppConfig(AppConfig):
    name = "myapp"

    def ready(self):
        import atexit
        atexit.register(tracker.close)
```

```python
# myapp/views.py
from .apps import tracker

def my_view(request):
    tracker.track("openai", "gpt-4o-mini", {"input_tokens": 10})
    ...
```
For a full setup guide, see [Django integration guide](docs/django.md).

### FastAPI

```python
from fastapi import FastAPI
from aicostmanager import Tracker

app = FastAPI()

@app.on_event("startup")
async def startup() -> None:
    app.state.tracker = Tracker()

@app.on_event("shutdown")
def shutdown() -> None:
    app.state.tracker.close()
```
For a full setup guide, see [FastAPI integration guide](docs/fastapi.md).

### Streamlit

```python
import streamlit as st
from aicostmanager import Tracker
import atexit

@st.cache_resource
def get_tracker():
    tracker = Tracker()
    atexit.register(tracker.close)
    return tracker

tracker = get_tracker()

if st.button("Generate"):
    tracker.track("openai", "gpt-4o-mini", {"input_tokens": 10})
```
For a full setup guide, see [Streamlit integration guide](docs/streamlit.md).

### Celery

```python
from celery import Celery
from aicostmanager import Tracker
from celery.signals import worker_shutdown

app = Celery("proj")
tracker = Tracker()

@app.task
def do_work():
    tracker.track("openai", "gpt-4o-mini", {"input_tokens": 10})

@worker_shutdown.connect
def close_tracker(**_):
    tracker.close()
```

For very short tasks, use `with Tracker() as tracker:` inside the task
to ensure flushing.

## More documentation

- [Usage Guide](docs/usage.md)
- [Tracker](docs/tracker.md)
- [Configuration](docs/config.md)
- [LLM wrappers](docs/llm_wrappers.md)
- [Persistent Delivery](docs/persistent_delivery.md)
- [Django integration](docs/django.md)
- [FastAPI integration](docs/fastapi.md)
- [Streamlit integration](docs/streamlit.md)
- [Full documentation index](docs/index.md)

