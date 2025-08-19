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

```python
from aicostmanager import Tracker

with Tracker() as tracker:
    tracker.track("openai", "gpt-4o-mini", {
        "input_tokens": 10,
        "output_tokens": 20,
    })
```

Using `with Tracker()` ensures the background delivery queue is flushed before
the program exits.

Configuration values are read from an ``AICM.INI`` file.  See
[`config.md`](docs/config.md) for the complete list of available settings and
their defaults.

## Choosing a delivery strategy

`Tracker` supports multiple delivery components via `DeliveryType`:

- **Immediate** – send each record synchronously. Ideal for simple scripts or
  tests.
- **In-memory queue** (`DeliveryType.MEM_QUEUE`) – buffer records in memory and
  deliver them in the background.
- **Persistent queue** (`DeliveryType.PERSISTENT_QUEUE`) – durable SQLite-backed
  queue for reliability across restarts.

Use the persistent queue for long-running services where losing usage data is
unacceptable, the in-memory queue for short-lived apps, and immediate delivery
when every call can block on the API. See
[Persistent Delivery](docs/persistent_delivery.md) and the
[Tracker guide](docs/tracker.md#choosing-a-delivery-manager) for details.

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
    app.state.tracker = await Tracker.create_async()

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
- [Persistent Delivery](docs/persistent_delivery.md)
- [Django integration](docs/django.md)
- [FastAPI integration](docs/fastapi.md)
- [Streamlit integration](docs/streamlit.md)
- [Full documentation index](docs/index.md)

