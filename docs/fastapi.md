# FastAPI Integration

This guide covers setting up the AICostManager tracker in a FastAPI
application.

## Install the SDK

```bash
uv pip install aicostmanager
# or
pip install aicostmanager
```

## Configuration file

Create an `AICM.INI` file in your project directory:

```ini
[aicostmanager]
AICM_API_KEY = sk-api01-...
# Optional overrides
AICM_DELIVERY_TYPE = PERSISTENT_QUEUE
AICM_DB_PATH = ./aicm.db
```

Expose the path through an environment variable or settings class:

```bash
export AICM_INI_PATH=/path/to/AICM.INI
```

## Application startup and shutdown

Initialise the tracker during startup so configuration loading does not block
individual requests. Use `Tracker.create_async` to perform setup in a worker
thread and close the tracker on shutdown:

```python
from fastapi import FastAPI
from aicostmanager import Tracker
import os

app = FastAPI()

@app.on_event("startup")
async def startup() -> None:
    ini_path = os.getenv("AICM_INI_PATH")
    app.state.tracker = await Tracker.create_async(ini_path=ini_path)

@app.on_event("shutdown")
def shutdown() -> None:
    app.state.tracker.close()
```

## Recording usage

Inside route handlers, use the tracker to send usage data:

```python
from fastapi import Request

@app.post("/track")
async def track_usage(request: Request) -> dict:
    payload = await request.json()
    app.state.tracker.track("openai", "gpt-4o-mini", payload)
    return {"status": "queued"}
```

If the payload construction is CPU heavy, `track_async` will offload it to a
worker thread:

```python
await app.state.tracker.track_async("openai", "gpt-4o-mini", payload)
```

With the tracker created at startup and closed on shutdown, FastAPI services
can report usage without blocking request handling.
