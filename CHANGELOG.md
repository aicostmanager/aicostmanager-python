# Changelog

All notable changes to this project will be documented in this file.

## [0.1.24] - 2025-01-27
### Enhanced
- **HeyGen Integration**: Comprehensive step-by-step documentation (`docs/heygen.md`) covering complete API integration workflow from session retrieval to cost tracking
- **HeyGen Testing**: Improved test coverage with separate session sets for immediate vs persistent delivery methods to prevent duplicate tracking
- **Deepgram Support**: Enhanced documentation and testing for websocket transcription and streaming text-to-speech services
- **Persistent Delivery**: Improved queue management leveraging automatic context manager flushing, reducing manual drainage wait logic while maintaining reliability

### Added
- Complete HeyGen API integration examples with both immediate and persistent delivery methods
- Production-ready HeyGen sync functions suitable for cron jobs and scheduled tasks
- Enhanced error handling and troubleshooting guidance for HeyGen API integration
- Improved test isolation ensuring each session is tracked only once across delivery types

### Fixed
- Simplified persistent queue drainage by better utilizing the automatic `stop()`/`close()` behavior in context managers
- Reduced unnecessary manual timeout logic while maintaining test reliability
- Updated import organization and code formatting consistency

## [0.1.23] - 2025-01-27
### Fixed
- `PersistentDelivery` logger initialization issue that caused `AttributeError: 'PersistentDelivery' object has no attribute 'logger'` when accessing the logger during database setup before parent class initialization
- Initialize logger early in `PersistentDelivery.__init__()` to ensure it's available for database operations and warning messages about failed queue items

### Added
- `track_llm_usage` and `track_llm_usage_async` methods for automatic usage
  extraction from LLM responses, with streaming helpers.
- `AICM_LIMITS_ENABLED` configuration to toggle triggered limit enforcement in
  delivery components.


## [0.1.18] - 2025-08-11
### Added

- REST API tracking guide (`docs/rest.md`) and example script `examples/heygen_sync.py` showing batch/manual tracking with `Tracker`
- Per-call context support in REST wrappers via `set_client_customer_key()` and `set_context()`

### Enhanced
- `UniversalExtractor`: base_url autodetection, streaming `final_fields` support, UUID generation for missing `response_id`, and broader JSON serialization (httpx.URL/urllib `ParseResult`, Pydantic `model_dump`, objects with `dict`/`__dict__`)
- `RestCostManager` and `AsyncRestCostManager`: pre-request triggered limit checks, delivery batching controls (`delivery_mode`, `on_full`, batch size/interval), and context manager helpers
- Documentation refreshed with REST wrapper usage and FastAPI tracker lifecycle guidance

### Fixed
- More defensive extraction error handling so failures never block delivery
- Minor documentation link/formatting consistency

## [0.1.15] - 2025-01-07
### Enhanced
- Documentation updated to be uv-first across the project (installation and dev workflows)
- README now recommends `uv pip install` / `uv add` for installation and adds queue health examples
- Usage guide now shows uv-first install instructions
- Build & Deploy guide updated to use `uv pip` for dev and release verification commands
- Testing guide aligned on `uv venv` and `uv pip` for dependency installs

### Added
- New `docs/config.md` covering configuration settings and defaults
- New `docs/tracker.md` with comprehensive manual usage tracking guide, validation, async init, and FastAPI lifecycle

### Fixed
- Changelog wording referencing pip updated to `uv pip install` where appropriate

## [0.1.14] - 2025-01-07
### Added
- **New `Tracker` class** for manual usage tracking with configurable validation schema
- `UsageValidationError` exception for robust type validation of tracked usage data
- `TypeValidator` utility for validating values against string-specified Python type hints
- Async factory method `Tracker.create_async()` for non-blocking tracker initialization in async applications
- `Tracker.close()` method for graceful shutdown of background delivery workers
- Enhanced delivery queue with overflow metrics and configurable discard callbacks
- Support for `AICM_DELIVERY_ON_FULL` environment variable to control queue overflow behavior globally

### Enhanced
- **Manual usage tracking capabilities** with schema-based validation for custom usage scenarios
- Delivery system performance improvements with persistent event loop reuse in async mode
- FastAPI integration examples with proper lifecycle management for tracker instances
- Comprehensive test coverage for new tracker functionality and validation scenarios
- Queue overflow handling with three modes: `block`, `raise`, or `backpressure` (with discard metrics)

### Fixed
- **Triggered limits retrieval** now properly fetches from API when local cache is missing or corrupted
- Improved reliability of end-to-end usage limit enforcement tests
- Better event loop management in delivery worker threads for async operations
- Enhanced config manager robustness when INI files lack required encrypted payloads

### Technical Improvements
- Added `on_discard` callback support for monitoring dropped payloads in delivery queues
- Persistent event loop management in delivery worker for better async performance
- Enhanced triggered limits initialization with automatic API fallback when cache is empty
- Comprehensive validation framework supporting complex Python type hints including `Optional`, `Union`, `List[T]`, and `Dict[K,V]`

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
- This resolves issues where `uv add aicostmanager` and `uv pip install aicostmanager` resulted in empty package installations
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