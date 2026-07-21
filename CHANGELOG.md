# Changelog

All notable changes to Guard Proxy are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Python distributions use the [PEP 440](https://peps.python.org/pep-0440/)
spelling of the same version (e.g. `0.1.0b2` for `0.1.0-beta.2`).

## [0.1.0-beta.2] - 2026-07-21

### Added

- Per-policy DDoS protection: configurable request rate limiting and
  concurrent-connection throttling applied at the HAProxy edge (#274).
- Config-only automatic IP banning for DDoS policies: repeat offenders are
  tracked and denied for a configurable duration, evaluated before the
  rate/connection deny rules.

### Changed

- The `/health` probe now reports the installed package version via
  `importlib.metadata` instead of a hardcoded string, giving the backend a
  single source of truth for its version.

## [0.1.0-beta.1] - 2026-07-21

### Added

- Image-only Compose release kit under `release/` (manifest, `.env` template,
  HAProxy reference config, install/upgrade guide) for running published
  images without the source tree.
- Publish workflow now tags beta images on the mutable `beta` channel and
  attaches the release-kit archive to a GitHub prerelease.

### Fixed

- The release-kit Compose stack uses its own project name to avoid clashing
  with a local development stack.

## [0.1.0-alpha] - 2026-07-07

### Added

- Initial alpha of the Guard Proxy WAF admin platform: HAProxy + Coraza data
  plane with a FastAPI admin API and a React frontend.
- Management of virtual hosts, security policies, rule overrides, rule
  exclusions, and custom rules, plus runtime config generation and apply.
- Coraza audit-log ingestion via the log-shipper sidecar.

[0.1.0-beta.2]: https://github.com/bihius/guard-proxy/compare/v0.1.0-beta.1...v0.1.0-beta.2
[0.1.0-beta.1]: https://github.com/bihius/guard-proxy/compare/v0.1.0-alpha...v0.1.0-beta.1
[0.1.0-alpha]: https://github.com/bihius/guard-proxy/releases/tag/v0.1.0-alpha
