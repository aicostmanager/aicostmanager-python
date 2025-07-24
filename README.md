# AICostManager Python SDK

AICostManager is an LLM usage tracking and cost control service. This SDK provides a simple wrapper that forwards your LLM client calls to [AICostManager](https://aicostmanager.com) so that usage can be analysed and limits enforced.

Sign up for an account and obtain an API key at [aicostmanager.com](https://aicostmanager.com). Without a valid key the tracking wrapper will not deliver usage data.

## ✨ Key Features

- Works with any Python LLM SDK – OpenAI, Anthropic Claude, Google Gemini, AWS Bedrock and more
- Privacy first: only usage metadata is sent to AICostManager, never your prompts or API keys
- Automatic background delivery with retry logic so that tracking does not block your application
- Stream aware: streaming responses are tracked once the stream completes
- Drop in replacement – wrap your existing client and continue to call it exactly as before

## 👤 Getting an API Key

1. Visit [aicostmanager.com](https://aicostmanager.com) and create a free account.
2. Generate an API key from the dashboard.
3. Export the key or pass it to `CostManager` directly.

```bash
export AICM_API_KEY="sk-your-api-key"
```

## 🚀 Quick Start

Install the SDK from PyPI:

```bash
pip install aicostmanager
```

Wrap your client:

```python
import openai
from aicostmanager import CostManager

openai_client = openai.OpenAI(api_key="OPENAI_API_KEY")
tracked_client = CostManager(openai_client)  # reads AICM_API_KEY from env

response = tracked_client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Tell me a dad joke."}],
)
print(response.choices[0].message.content)
```

### Streaming

```python
stream = tracked_client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Tell me a dad joke."}],
    stream=True,
)
for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## 👨‍💻 Querying Events

Usage data delivered to `/track-usage` can be viewed via the `/usage/events/` API. The helper below fetches recent events and searches for a specific `response_id`:

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

## 📦 How Delivery Works

`CostManager` places extracted usage payloads on a global queue. A background worker batches and retries delivery so that instrumentation never blocks your application. The queue size, retry attempts and request timeout can be tuned when constructing the wrapper. The asynchronous variants share the same behaviour.

## 💻 Running the Tests

1. Create a `.env` file inside `tests/` with at least `AICM_API_KEY` and any provider keys you wish to use:

   ```env
   AICM_API_KEY=your-aicostmanager-api-key
   OPENAI_API_KEY=your-openai-api-key
   # optional overrides
   # AICM_API_BASE=https://aicostmanager.com
   # AICM_INI_PATH=/path/to/AICM.ini
   ```

2. Install the test dependencies (requires [`uv`](https://github.com/astral-sh/uv) or `pip`):

   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -e . openai pytest python-dotenv
   ```

3. Run the suite:

   ```bash
   pytest
   ```

See the [docs](docs/index.md) for additional usage examples and details about the tracking configuration.
