# Changelog

All notable changes to this project will be documented in this file.

## [0.1.8] - 2025-01-30
### Fixed
- Fixed syntax error in `test_async_client.py` where elif statement had incorrect indentation
- Fixed config manager test mock functions to properly accept `etag` parameter
- Added missing `configs_etag` attribute and property to `AsyncCostManagerClient` class
- Fixed real test failures in `test_anthropic_real_cost_manager.py` by adding triggered limits cleanup
- Resolved ETag payload validation issues in comprehensive testing scenarios

### Added
- Comprehensive ETag functionality test suite (`test_real_endpoints_etag.py`) with 13 real API tests
- New `clear_triggered_limits` fixture in `conftest.py` for cleaner test isolation
- Manual ETag manipulation and corruption recovery testing capabilities
- Direct server response validation for invalid ETag scenarios

### Enhanced
- ETag caching functionality now thoroughly validated with real server interactions
- Both sync and async client ETag behavior verification across multiple test scenarios
- INI file lifecycle testing (creation, corruption, recovery, validation)
- Test coverage for edge cases including empty ETags, concurrent access, and multiple refresh cycles

## [0.1.7] - 2025-01-30
### Fixed
- Fixed URL serialization issue in `_make_json_serializable` method for httpx.URL objects
- Resolved 422 validation errors when tracking usage for OpenAI-compatible APIs (DeepSeek, Gemini)
- Fixed usage event delivery failures that were preventing proper cost tracking
- All OpenAI and OpenAI-compatible real endpoint tests now pass successfully

## [0.1.6] - 2025-01-27
### Added
- Comprehensive usage limit functionality with real-time enforcement
- `UsageLimitExceeded` exception for blocking API calls when limits are hit
- End-to-end integration testing across multiple LLM providers
- Enhanced event delivery verification in test suite

### Enhanced
- Real endpoint testing infrastructure for Bedrock and other providers
- Triggered limits persistence and configuration management
- Error handling with detailed limit information and blocking behavior

## [0.1.5] - 2025-07-24
### Changed
- Added /dist/* to gitignore
- Updated `TriggeredLimit` structure. Vendor details now provide
  `config_id_list` and `hostname` values. The old `vendor` string field
  has been removed.

## [0.1.3] - 2025-07-24
### Added
- Initial release of the AICostManager Python SDK
- Cost tracking wrapper for popular LLM SDKs
- Background delivery queue with retry logic
- Configuration via environment variables

## [0.1.0] - 2025-07-24
### Added
- False start