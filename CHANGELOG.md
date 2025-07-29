# Changelog

All notable changes to this project will be documented in this file.

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