# Tracker

The new `Tracker` works with `PersistentDelivery` to send usage information to
the `/track` endpoint.  It does not require configuration metadata from the
server and simply forwards payloads supplied by the caller.

## Tracking Usage

```python
from aicostmanager import Tracker

tracker = Tracker(aicm_api_key="sk-test")

usage = {"input_tokens": 1, "output_tokens": 2}
tracker.track("openai", "gpt-5-mini", usage)
```

Use `track_sync` to send immediately without waiting for the background queue:

```python
tracker.track_sync("openai", "gpt-5-mini", usage)
```

Both methods also have async counterparts `track_async` and `track_sync_async`
for use in frameworks such as FastAPI or when running inside Celery tasks.
Remember to call `close()` on application shutdown so any background worker can
terminate cleanly.
