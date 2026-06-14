# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Optional display name support in setup and options flows.
- Legacy certificate migration from shared paths to per-device certificate paths.
- Deprecated certificate configuration detection with persistent user notifications.
- Connection status diagnostic sensor.
- PR CI changelog enforcement check.

### Changed
- Per-device certificate handling is now the default behavior.
- Improved config flow validation, translation coverage, and device naming behavior.
- Backoff handling now escalates failures up to 15 minutes and sets error state.

## [0.2.0] - 2026-06-14

### Added
- Device-specific certificate generation and storage.
- Persistent LFDI availability even when initial meter polling fails.
- Legacy migration path for centralized certificate configurations.
- Optional friendly display name for meter entries.
- Expanded translation keys for config/options/entity text.

### Changed
- Release metadata/version alignment for Home Assistant manifest and package version.
- CI workflow now exposes separate required checks for lint/tests and changelog validation.

### Security
- Certificate migration preserves key material while moving toward isolated per-device certificate directories.
