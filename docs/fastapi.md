# FastAPI Integration

This guide covers setting up the AICostManager tracker in a FastAPI
application.

## Install the SDK

```bash
uv pip install aicostmanager
# or
pip install aicostmanager
```

## Environment Configuration

Set your API key as an environment variable:

```bash
export AICM_API_KEY=sk-api01-...
```

## Application startup and shutdown

Use FastAPI's lifespan context manager for proper tracker lifecycle management.
For reliable delivery in web applications, we recommend using `PersistentDelivery`:

```python
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from aicostmanager import Tracker, PersistentDelivery

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up AICM tracker...")
    try:
        # Create persistent delivery with intelligent defaults
        # - API key from AICM_API_KEY environment variable
        # - Database path: ~/.cache/aicostmanager/delivery_queue.db
        # - All other settings use sensible defaults
        persistent_delivery = PersistentDelivery()
        
        # Create tracker with persistent delivery
        app.state.tracker = Tracker(delivery=persistent_delivery)
        logger.info("AICM tracker initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize AICM tracker: {e}")
        app.state.tracker = None

    yield

    # Shutdown
    if hasattr(app.state, "tracker") and app.state.tracker:
        logger.info("Shutting down AICM tracker...")
        try:
            app.state.tracker.close()
            logger.info("AICM tracker closed successfully")
        except Exception as e:
            logger.error(f"Error closing AICM tracker: {e}")

# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)
```

### Alternative: Simple immediate delivery

For basic use cases where you don't need persistent queuing:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up AICM tracker...")
    try:
        # Simple tracker with immediate delivery
        # API key from AICM_API_KEY environment variable
        app.state.tracker = Tracker()
        logger.info("AICM tracker initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize AICM tracker: {e}")
        app.state.tracker = None

    yield

    # Shutdown
    if hasattr(app.state, "tracker") and app.state.tracker:
        logger.info("Shutting down AICM tracker...")
        try:
            app.state.tracker.close()
            logger.info("AICM tracker closed successfully")
        except Exception as e:
            logger.error(f"Error closing AICM tracker: {e}")

app = FastAPI(lifespan=lifespan)
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
