# AICostManager Python SDK

Track API usage and enforce cost controls by forwarding your LLM client calls to [AICostManager](https://aicostmanager.com).  The package exposes a minimal HTTP client for interacting with the service and a `CostManager` wrapper that can instrument other SDKs.

## Installation

### Using `uv`

```bash
# install uv if needed - see https://github.com/astral-sh/uv
uv venv          # create virtual environment in .venv
source .venv/bin/activate
uv pip install -e .
```

### Using `pip`

```bash
pip install aicostmanager
```

## Quick start with OpenAI

The tests in this repository wrap the [`openai` Python library](https://github.com/openai/openai-python).  Below mirrors that pattern.

```python
import openai
from aicostmanager import CostManager

openai_client = openai.OpenAI(api_key="OPENAI_API_KEY")
tracked = CostManager(openai_client, aicm_api_key="AICM_API_KEY")

response = tracked.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "system", "content": "Tell me a dad joke."}],
    max_tokens=50,
)
print(response.choices[0].message.content)
```

### Streaming

```python
stream = tracked.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "system", "content": "Tell me a dad joke."}],
    max_tokens=50,
    stream=True,
)
for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## Querying events

Usage records pushed to `/track-usage` can be viewed through the `/usage/events/` endpoint.  The snippet below fetches the most recent events and searches for a specific `response_id`.

```python
import requests

def find_event(aicm_api_key: str, aicm_api_base: str, response_id: str):
    headers = {"Authorization": f"Bearer {aicm_api_key}"}
    resp = requests.get(
        f"{aicm_api_base}/api/v1/usage/events/",
        headers=headers,
        params={"limit": 20},
        timeout=10,
    )
    resp.raise_for_status()
    for event in resp.json().get("results", []):
        if event.get("response_id") == response_id:
            return event
    return None
```

## How delivery works

`CostManager` places extracted usage payloads onto a global queue.  A background worker thread batches and retries delivery to `/track-usage` so that instrumentation never blocks your application.  The queue size, retry attempts and request timeout can be tuned when constructing the wrapper.  Asynchronous variants share the same behaviour.

## Running the tests

1. Create a `.env` file in `tests/` containing the following keys:

   ```env
   AICM_API_KEY=your-aicostmanager-api-key
   OPENAI_API_KEY=your-openai-api-key
   # optional overrides
   # AICM_API_BASE=https://aicostmanager.com
   # AICM_INI_PATH=/path/to/AICM.ini
   ```

   An active key from [aicostmanager.com](https://aicostmanager.com) is required; without it the wrapper will not deliver usage data.

2. Install dependencies and the test extras using `uv`:

   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -e . openai pytest python-dotenv
   ```

3. Run the suite:

   ```bash
   pytest
   ```

See [docs/usage.md](docs/usage.md) and [docs/tracking.md](docs/tracking.md) for more detail.
