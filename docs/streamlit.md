# Streamlit Integration

This guide explains how to track usage from a Streamlit application.

## Install the SDK

```bash
uv pip install aicostmanager
# or
pip install aicostmanager
```

## Configuration file

Create an `AICM.INI` file next to your Streamlit script:

```ini
[aicostmanager]
AICM_API_KEY = sk-api01-...
# Optional overrides
AICM_DELIVERY_TYPE = PERSISTENT_QUEUE
```

Store the path in `.streamlit/secrets.toml` so it is available at runtime:

```toml
# .streamlit/secrets.toml
AICM_INI_PATH = "./AICM.INI"
```

## Creating a cached tracker

Use `st.cache_resource` to construct the tracker once per process and close it
on exit:

```python
import streamlit as st
from aicostmanager import Tracker
import atexit

@st.cache_resource
def get_tracker() -> Tracker:
    tracker = Tracker(ini_path=st.secrets.get("AICM_INI_PATH"))
    atexit.register(tracker.close)
    return tracker

tracker = get_tracker()
```

## Recording usage

Call the tracker when handling user actions:

```python
def main():
    if st.button("Generate"):
        tracker.track("openai::gpt-4o-mini", {"input_tokens": 10})
        st.write("queued")

if __name__ == "__main__":
    main()
```

For short-lived scripts you can also use `with Tracker() as t:` to automatically
flush the queue.
