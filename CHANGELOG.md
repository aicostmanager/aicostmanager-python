# Changelog

All notable changes to this project will be documented in this file.

## [0.1.13] - 2025-01-06
### Enhanced
- Updated build and deployment documentation with comprehensive step-by-step release process
- Added detailed prerequisites, troubleshooting, and verification steps for releases
- Improved documentation for `bump-my-version` integration and GitHub Actions workflow
- Added quick reference commands for common release tasks

## [0.1.12] - 2025-01-05
### Fixed
- **CRITICAL**: Fixed empty package builds by correcting setuptools package discovery configuration
- Packages built with previous versions (0.1.10 and earlier) contained only metadata without actual Python source code
- This resolves issues where `uv add aicostmanager` and `pip install aicostmanager` resulted in empty package installations
- Updated `pyproject.toml` to properly include source files in wheel distributions

## [0.1.11] - 2025-08-04
### Fixed
- Fixed the version number in the __init__


## [0.1.10] - 2025-08-04
### Added
- Custom client metadata support with `client_customer_key` and `context` parameters
- New `set_client_customer_key()` and `set_context()` methods for all cost manager classes
- Automatic augmentation of usage payloads with client metadata for tracking and identification
- Client metadata support across all cost manager types: `CostManager`, `AsyncCostManager`, `RestCostManager`, and `AsyncRestCostManager`

### Enhanced
- Updated project dependencies to latest versions for improved compatibility and security
- Enhanced test coverage with comprehensive client metadata validation across all LLM providers
- Improved payload tracking with consistent metadata injection across sync and async operations

### Technical Improvements
- Unified `_augment_payload()` method implementation across all cost manager classes
- Comprehensive test suite covering client metadata functionality for OpenAI, Anthropic, Bedrock, Gemini, and OpenAI-compatible providers
- Enhanced delivery verification tests to validate client metadata presence in usage events

## [0.1.9] - 2025-01-30
### Fixed
- Fixed triggered limits initialization reliability during `CostManagerClient` instantiation
- Resolved test execution order dependency in `test_usage_limit_end_to_end` that caused intermittent failures
- Fixed global delivery state interference between test suites by adding proper test isolation
- Prevented spurious "ini" file creation in project root directory during mock testing
- Enhanced environment variable cleanup in client configuration tests

### Enhanced
- Improved triggered limits lifecycle management with consistent ETag-based fetching logic
- Strengthened client initialization to always call `/configs` endpoint and conditionally fetch `/triggered-limits`
- Enhanced config manager alignment with client initialization for better state consistency
- Added robust test isolation with `clean_delivery` fixture to prevent cross-test pollution
- Improved mock test safety by preventing file system operations with literal "ini" paths

### Added
- `RestCostManager` class for tracking costs of generic REST API calls using `requests.Session`
- `AsyncRestCostManager` class for tracking costs of async REST API calls using `httpx.AsyncClient`
- Universal REST API cost tracking capabilities for non-LLM services and custom APIs
- Support for tracking HTTP method calls (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS) with automatic usage extraction

### Technical Improvements
- All 81 core tests now pass reliably regardless of execution order
- Usage limit enforcement works consistently across different test scenarios
- Better separation between mock and real client behavior in test environment
- Enhanced triggered limits state management in INI file persistence layer

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