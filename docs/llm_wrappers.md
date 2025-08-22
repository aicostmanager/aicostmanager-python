# LLM Wrappers

AICostManager provides drop-in wrappers for popular large language model (LLM)
SDK clients. Each wrapper embeds a :class:`~aicostmanager.tracker.Tracker`
so every call automatically records usage without requiring any additional code.
You continue to interact with the native client methods and properties while the
wrapper forwards the usage data in the background.

Wrappers automatically derive the ``service_key`` sent to the tracker from the
model you pass to the underlying client. The corresponding ``api_id`` for the
provider is built in.

The service key format is ``[vendor]::[model]``. For the OpenAI Chat wrapper the
vendor is inferred from the client's ``base_url`` so compatible providers like
Fireworks or xAI are attributed correctly. The other wrappers use fixed vendors:
``openai``, ``anthropic``, ``google`` and ``amazon-bedrock``.

## Supported providers

| Wrapper | Native client | ``api_id`` |
| ------- | ------------- | ---------- |
| ``OpenAIChatWrapper`` | ``openai.OpenAI`` | ``openai_chat`` |
| ``OpenAIResponsesWrapper`` | ``openai.OpenAI`` | ``openai_responses`` |
| ``AnthropicWrapper`` | ``anthropic.Anthropic`` | ``anthropic`` |
| ``GeminiWrapper`` | ``google.generativeai.GenerativeModel`` | ``gemini`` |
| ``BedrockWrapper`` | ``boto3.client('bedrock-runtime')`` | ``bedrock`` |

## Basic usage

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

wrapper.close()  # flush any queued tracking data
```

The wrapper proxies every attribute on the client, so existing code typically
requires only one extra line to instantiate the wrapper.  A tracker is created
internally using the ``AICM_API_KEY`` environment variable.  Pass ``aicm_api_key``
or ``tracker`` to the wrapper constructor to override this behaviour.

## Streaming responses

Wrappers handle streaming automatically.  Iterate over the returned stream just
as you would with the native client and usage will be tracked once the final
chunk containing usage arrives.

```python
stream = wrapper.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a short poem"}],
    stream=True,
    stream_options={"include_usage": True},
)

for event in stream:
    if event.type == "message.delta" and event.delta.get("content"):
        print(event.delta["content"], end="")
print()
```

## Asynchronous clients

If the underlying SDK provides ``async`` methods, the wrappers preserve that
behaviour:

```python
async def run():
    resp = await wrapper.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(resp.choices[0].message.content)
```

Streaming async iterables are also supported and will be tracked in the same
way.

## Other providers

Replace ``OpenAIChatWrapper`` with one of the other provider-specific wrappers
and supply the appropriate native client:

```python
from aicostmanager import (
    OpenAIResponsesWrapper,
    AnthropicWrapper,
    GeminiWrapper,
    BedrockWrapper,
)

# OpenAI Responses
resp_wrapper = OpenAIResponsesWrapper(client)
resp_wrapper.responses.create(...)

# Anthropic
import anthropic
anth_wrapper = AnthropicWrapper(anthropic.Anthropic())
anth_wrapper.messages.create(model="claude-3-haiku-20240307", ...)

# Gemini
import google.generativeai as genai
genai.configure()
gem_wrapper = GeminiWrapper(genai.GenerativeModel("gemini-1.5-flash"))
result = gem_wrapper.generate_content("hello")

# Bedrock
import boto3
bed_client = boto3.client("bedrock-runtime", region_name="us-east-1")
bed_wrapper = BedrockWrapper(bed_client)
bed_wrapper.invoke_model(modelId="anthropic.claude-v2", body={"prompt": "hi"})
```

The wrapper's ``close`` method should be invoked during application shutdown to
ensure any buffered tracking data is delivered.
