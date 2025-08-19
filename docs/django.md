# Django Integration

This guide shows how to add cost tracking to a Django project using the
AICostManager SDK.

## Install the SDK

```bash
uv pip install aicostmanager
# or
pip install aicostmanager
```

## Configuration file

1. Create an `AICM.INI` file in your project root:

```ini
[aicostmanager]
AICM_API_KEY = sk-api01-...
# Optional overrides
AICM_DELIVERY_TYPE = MEM_QUEUE
AICM_LOG_FILE = aicm.log
```

2. Register the file path in `settings.py` so other components can reference
   it:

```python
# settings.py
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
AICM_INI_PATH = BASE_DIR / "AICM.INI"
```

The tracker will automatically load configuration from this file when the path
is supplied.

## Initialising the tracker

Create a tracker when Django starts and close it when the process exits. An
app configuration is a convenient place:

```python
# myapp/apps.py
from django.apps import AppConfig
from django.conf import settings
from aicostmanager import Tracker
import atexit

class MyAppConfig(AppConfig):
    name = "myapp"

    def ready(self):
        self.tracker = Tracker(ini_path=getattr(settings, "AICM_INI_PATH", None))
        atexit.register(self.tracker.close)
```

Access the tracker from views:

```python
# myapp/views.py
from django.apps import apps


def my_view(request):
    tracker = apps.get_app_config("myapp").tracker
    tracker.track("openai", "gpt-4o-mini", {"input_tokens": 10})
    ...
```

## Asynchronous views

For async views, call `track_async` to run tracking in a worker thread:

```python
async def my_async_view(request):
    tracker = apps.get_app_config("myapp").tracker
    await tracker.track_async("openai", "gpt-4o-mini", {"input_tokens": 10})
```

With these pieces in place, the tracker will flush queued usage when Django
shuts down, ensuring reliable cost reporting.
