# Changelog

All notable changes to Guard Proxy are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Python distributions use the [PEP 440](https://peps.python.org/pep-0440/)
spelling of the same version (e.g. `0.1.0b2` for `0.1.0-beta.2`).

## [Unreleased]

### Changed

- Third-party images are pinned to an exact version and digest instead of
  floating tags: HAProxy `3.0.29`, coraza-spoa `0.6.1`, Alpine `3.19.9`,
  PostgreSQL `16.15`, Python `3.13.16` (Debian trixie) and Node `24.21.0`.
  The backend now installs exactly the HAProxy release the `haproxy`
  container runs, so `POST /config/apply` validates generated configs with
  the same HAProxy that loads them. A new `version-pins` CI job fails on
  unpinned or diverging pins. Release-kit users get the pinned `haproxy` and
  `postgres` images on their next `docker compose pull`; `postgres` moves
  only within the 16 series, so existing data volumes keep working.
- The evaluation lab runs three tests on two targets: the tagged corpus on
  WordPress (`wp.local`), go-ftw on Albedo (`ftw.local`), and the wrk load test
  on Albedo. Juice Shop, DVWA, OWASP ZAP and Nuclei are removed: the scanners
  gave no TP/FN/TN/FP denominator, and Juice Shop crashed under load.
- The benign corpus is a set of real WordPress requests, including POST forms,
  a JSON body, and legitimate text with SQL words, quotes and a code snippet;
  every attack payload is sent in a query parameter and in a POST body.
- The load test targets Albedo instead of Juice Shop, adds POST requests to the
  mix, records direct-path latency, and marks a run with errors as invalid.
- The PL1 and PL2 lab profiles are fixed in `benchmarks/lab/policy-profiles.sh`
  and differ only in paranoia level: inbound threshold 5, outbound threshold 4,
  block mode, rate limiting and GeoIP off. `make set-policy` refuses to run when
  `benchmarks/lab/.env` still sets other `LAB_POLICY_*`/`LAB_PL2_POLICY_*`
  values or a lab policy has exclusions, overrides or custom rules, and reads
  every profile field back after applying it. `summary.json` also records the
  policy's rate limiting, GeoIP mode and tuning counts.
- The load test can use a separate client started by hand (`LOAD_CLIENT=manual`,
  `LOAD_SERVER_ADDR`): for each run the runner prints the `wrk` command, waits
  for Enter to start resource sampling, and reads the pasted wrk output. The
  HTTP traffic goes over the network to HAProxy and to Albedo's baseline port
  (`LAB_FTW_DIRECT_BIND`, `LAB_FTW_DIRECT_PORT`, default `127.0.0.1:18080`).
  `performance.json` records the mode and both URLs.
- `make eval-sweep` stops at the first failing step and passes the `LOAD_*`
  variables on to the load runner.
- Resource samples record the achieved sampling interval, the sample count
  and the sampled window next to the target interval.

### Fixed

- Coraza parses JSON and XML request bodies with the matching body processor
  and rejects bodies that fail to parse (rules 200000–200002 and 200006 from
  Coraza's recommended configuration). Before, a JSON body was read as one
  URL-encoded argument name, so any JSON request was blocked as SQL injection
  at PL2 and JSON fields were not inspected one by one.
- go-ftw runs in log mode. In cloud mode every CRS test that asserts no HTTP
  status passed without a check, so the reported conformance (99.8 %) did not
  depend on the WAF. Tests for rules above the policy's paranoia level and for
  response rules are excluded and counted separately.
- Container memory reported in GiB by `docker stats` was recorded as MiB in
  the load test's resource samples.
- `make lab-up` installs WordPress. The `wp-cli` command was split across
  lines by YAML folding, so WordPress stayed uninstalled and the corpus hit the
  installer redirect.

## [0.1.0-beta.6] - 2026-10-07

### Fixed

- Config apply no longer answers requests with 503 when it introduces a new
  WAF policy. Coraza loads a policy's application only after HAProxy had
  already started sending its name, and coraza-spoa fails closed on an
  unknown application. Apply now waits until Coraza serves every new
  application before reloading HAProxy; if Coraza does not load them within
  `CORAZA_RELOAD_TIMEOUT_SECONDS` (default 30), the previous release is
  restored and `POST /config/apply` returns the new status
  `coraza_reload_failed` (HTTP 500). Applications a release drops stay
  loaded until HAProxy has stopped sending them. An apply that introduces a
  policy now takes a second or two longer.
- The CRS compliance benchmark renders go-ftw config values before running.

## [0.1.0-beta.5] - 2026-10-03

### Fixed

- Each vhost is now inspected with its own policy. Every policy assigned to
  an active vhost runs as a separate Coraza application with its own
  enforcement mode, paranoia level, anomaly thresholds, rule overrides,
  exclusions, and custom rules; HAProxy picks the application per vhost.
  Before, all vhosts shared one WAF configuration, and assigning different
  policies to two vhosts made config apply fail. Vhosts without a policy are
  inspected with CRS defaults in detect-only mode.
- Config apply no longer interrupts traffic: Coraza reloads its rules with
  `SIGHUP` instead of restarting, so requests during an apply are no longer
  answered with 503 (#303).

### Changed

- Runtime releases contain a generated `coraza-spoa.yaml` and per-policy
  `coraza/<application>/` directories instead of a single `crs-setup.conf`
  and `rule-overrides.conf`. The `POST /config/apply` response returns
  `generated_config.coraza_spoa_yaml` and `generated_config.coraza_apps`
  instead of `crs_setup_conf` and `rule_overrides_conf`. After upgrading,
  apply the configuration once; until then the previous single-policy
  release stays active.
- Coraza memory use grows with the number of distinct policies assigned to
  vhosts, since each application loads the full CRS rule set.
- Path-scoped policy bindings that point at a policy other than the vhost's
  own are rejected by config generation instead of being merged into one
  global policy.
- New `CORAZA_LOG_LEVEL` backend setting for the generated Coraza
  configuration; `make dev` sets it to `debug`.
- Evaluation lab: every lab vhost has its own policy (`Lab <domain>`)
  instead of all four sharing `Lab Baseline`. `make set-policy POLICY=pl1|pl2`
  writes the profile's paranoia level and thresholds into those policies,
  optionally for one vhost (`TARGET_VHOST=wp.local`), and each runner records
  the policy that actually protects its target in `summary.json`.
  `LAB_POLICY_NAME` and `LAB_PL2_POLICY_NAME` are no longer used.

## [0.1.0-beta.4] - 2026-09-25

### Added

- GeoIP country filtering per policy: allowlist or blocklist of ISO country
  codes, enforced in HAProxy from a daily-refreshed ip66.dev database (no
  license key needed; `GEOIP_*` settings in `.env`).
- Learning mode: for policies in detect-only mode, a nightly job (or
  **Analyze now** on the policy page) groups repeated rule matches on the
  same input and proposes rule exclusions with a 0–100 false-positive
  confidence. An admin reviews, approves or permanently rejects each one;
  nothing is applied automatically. Adds the `tuning_suggestions` table
  (run `alembic upgrade head`).
- Create a rule exclusion directly from a WAF event: **Create exclusion** in
  the log detail view opens the exclusion form pre-filled with the rule, the
  variable it matched and the request path.
- Rule exclusions can target more Coraza variables (header and cookie names,
  cookies, raw request URI, request filename).
- The dashboard is now a security operations screen: WAF event activity
  chart, blocked/critical/monitored counts with window-over-window change,
  top rules and source IPs linking into the log viewer, recent blocks and
  deployment status, over 1h/24h/7d/30d. Backed by new `/stats` endpoints.

### Changed

- Custom rules, rule exclusions and path scopes are validated when they are
  saved (422 with a readable message) instead of only when the configuration
  is generated.

### Fixed

- **Security:** custom rules using regex escapes (`\d`, `\.`, `\s`, …) never
  matched, because backslashes were doubled when the rule was written to
  Coraza. Such rules now match as written. Values ending in a backslash or
  containing `\"` are rejected, as they cannot be expressed in the rule
  syntax.
- **Security:** a path-scoped rule exclusion for `/rest/products` also
  applied to `/rest/productsXYZ` and `/rest/products-admin`; scopes now match
  whole path segments.
- Binding vhosts to more than one active policy made **Apply config** fail
  with a bare 500 while the dashboard still showed the config as deployed.
  Apply now explains the limit (one active CRS policy), and the dashboard
  shows why the configuration cannot be generated.
- Any validation error (422) replaced the whole page with an "Unexpected
  Application Error" instead of showing the message in the form.
- The logs table, event details, runtime status and vhost dates showed UTC
  times as if they were local time.
- The policy detail page now shows GeoIP, DDoS and auto-ban settings; auto-ban
  is shown as active only when DDoS protection is on (otherwise it has no
  effect).
- Evaluation lab: load tests restart the target before each run and use only
  requests the target answers with 2xx, the metrics parser reads exact
  percentiles, and the ZAP baseline scan works against vhost targets.

## [0.1.0-beta.3] - 2026-07-27

### Added

- Banned IPs admin page: table of source IPs currently blocked by the
  auto-ban mechanism (IP, domain, violations, expires-in), with search,
  client-side pagination, and an admin-gated Unban action backed by the
  HAProxy Runtime API.
- Dashboard stat card showing the current count of actively banned IPs.

### Changed

- Policy form now hides the DDoS/auto-ban sub-fields entirely until their
  parent toggle is enabled, instead of just disabling them; disabling DDoS
  protection also clears the auto-ban toggle so it can't stay enabled
  invisibly.

### Fixed

- `GET /security/banned-ips` and the Unban action no longer return `502`
  when a vhost's auto-ban stick-table hasn't been provisioned by HAProxy
  yet — an unprovisioned table is now treated as an empty ban list.
- The "Apply config" button no longer stays stuck visible after a plain
  backend restart with no pending changes; the deployed config's checksum
  is now reconciled against the runtime operation log on every startup.

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

[0.1.0-beta.6]: https://github.com/bihius/guard-proxy/compare/v0.1.0-beta.5...v0.1.0-beta.6
[0.1.0-beta.5]: https://github.com/bihius/guard-proxy/compare/v0.1.0-beta.4...v0.1.0-beta.5
[0.1.0-beta.4]: https://github.com/bihius/guard-proxy/compare/v0.1.0-beta.3...v0.1.0-beta.4
[0.1.0-beta.3]: https://github.com/bihius/guard-proxy/compare/v0.1.0-beta.2...v0.1.0-beta.3
[0.1.0-beta.2]: https://github.com/bihius/guard-proxy/compare/v0.1.0-beta.1...v0.1.0-beta.2
[0.1.0-beta.1]: https://github.com/bihius/guard-proxy/compare/v0.1.0-alpha...v0.1.0-beta.1
[0.1.0-alpha]: https://github.com/bihius/guard-proxy/releases/tag/v0.1.0-alpha
