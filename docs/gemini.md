# Gemini Usage Tracking

This document covers usage tracking for Google's Gemini models in the AI Cost Manager library.

## Overview

The Gemini API provides comprehensive usage information through the `usageMetadata` or `usage_metadata` field in API responses. The AI Cost Manager library automatically extracts and normalizes this information for consistent tracking across different response formats.

## Usage Fields

The Gemini API exposes the following usage fields:

### Core Token Counts
- **`promptTokenCount`**: Number of tokens in the prompt (user input)
- **`candidatesTokenCount`**: Number of tokens in the generated response
- **`totalTokenCount`**: Sum of prompt and candidate tokens

### Advanced Features
- **`cachedContentTokenCount`**: Number of tokens served from cache (for cached content)
- **`toolUsePromptTokenCount`**: Number of tokens used for tool/function calling prompts
- **`thoughtsTokenCount`**: Number of tokens used for model thinking/reasoning (in thinking models)

### Detailed Breakdowns
- **`promptTokensDetails`**: Array with per-modality breakdown of prompt tokens (text, image, etc.)
- **`candidatesTokensDetails`**: Array with per-modality breakdown of response tokens
- **`cacheTokensDetails`**: Array with breakdown of cached token usage

## Usage Extraction

### Non-Streaming Responses

For standard (unary) requests, usage metadata is available immediately:

```python
import google.genai as genai
from aicostmanager import GeminiWrapper

client = genai.Client(api_key="your-key")
wrapped_client = GeminiWrapper(client)

response = wrapped_client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Hello, world!"
)

# Usage is automatically tracked
print("Usage tracked:", response)  # The wrapper handles tracking transparently
```

### Streaming Responses

For streaming requests, usage metadata is only available in the final chunk:

```python
stream = wrapped_client.models.generate_content_stream(
    model="gemini-2.5-flash",
    contents="Tell me a story"
)

for chunk in stream:
    print(chunk.text, end="")  # Print streaming response

# Usage is automatically extracted from the final chunk and tracked
```

## Normalization

The library automatically normalizes Gemini usage data to ensure consistent field names and formats:

- **camelCase** fields (`usageMetadata`) are converted to **camelCase** output
- **snake_case** fields (`usage_metadata`) are converted to **camelCase** output
- All usage fields are extracted and made available for tracking
- Null/None values are filtered out

### Example Normalized Usage

```json
{
  "promptTokenCount": 12,
  "candidatesTokenCount": 38,
  "totalTokenCount": 50,
  "cachedContentTokenCount": 5,
  "toolUsePromptTokenCount": 0,
  "thoughtsTokenCount": 0,
  "promptTokensDetails": [...],
  "candidatesTokensDetails": [...],
  "cacheTokensDetails": [...]
}
```

## Response ID Tracking

The library attempts to extract response IDs from multiple possible field names for better correlation with Google logs:

- `id` (standard)
- `response_id` (snake_case)
- `responseId` (camelCase)

## Integration with Cost Tracking

Usage data is automatically sent to the AI Cost Manager service with the following information:

- **API ID**: `gemini`
- **Service Key**: `google::{model-name}`
- **Usage Data**: Normalized token counts and metadata
- **Response ID**: For correlation with API logs

## Error Handling

The library includes robust error handling for:

- Missing or malformed usage metadata
- Network interruptions during streaming
- Mock objects in testing scenarios
- Different SDK versions and response formats

## Testing

Comprehensive tests are included for:

- Non-streaming usage extraction
- Streaming usage extraction (final chunk only)
- Normalization of both camelCase and snake_case inputs
- Error handling for malformed responses
- Integration with the tracking system

Run tests with:

```bash
pytest tests/test_gemini_real_tracker.py
pytest tests/tracker/deliver_now_streaming/test_gemini_deliver_now_streaming.py
```
