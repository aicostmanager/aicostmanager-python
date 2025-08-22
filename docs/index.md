# AICostManager Documentation

To use the SDK you must create a free account at [AICostManager](https://aicostmanager.com)
and generate an API key. Set it in the `AICM_API_KEY` environment variable or
pass it directly to the client or tracker.

## User Guides

- [Usage](usage.md) - Basic SDK usage and API examples
- [Manual Usage Tracking](tracker.md) - Record custom usage events
- [LLM Wrappers](llm_wrappers.md) - Drop-in clients that track usage automatically
- [Configuration](config.md) - Settings and defaults
- [Limit Managers](limit_managers.md) - Manage usage limits and triggered limits
- [Django](django.md) - Integrate with Django projects
- [FastAPI](fastapi.md) - Integrate with FastAPI applications
- [Streamlit](streamlit.md) - Track usage from Streamlit apps

## Development

- [Testing](testing.md) - Running tests and validation
- [Build & Deploy](build_and_deploy.md) - Release process and deployment

## Reference

- [Changelog](../CHANGELOG.md) - Version history and changes
- [Live OpenAPI schema](/api/v1/openapi.json) - Generated API specification
