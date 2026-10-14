# Changelog

All notable changes to Guard Proxy are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Python distributions use the [PEP 440](https://peps.python.org/pep-0440/)
spelling of the same version (e.g. `0.1.0b2` for `0.1.0-beta.2`).

## [Unreleased]

### Changed

- GitHub Actions are pinned to commit SHAs instead of mutable tags, and every
  workflow declares a `permissions:` block (CI and the smoke run are read-only;
  publishing keeps `contents: read` and `packages: write`). A tag such as `@v4`
  can be repointed by whoever controls the action repository, which would run
  their code with this repository's workflow token. The `version-pins` check now
  fails on a workflow action that is not pinned and on a workflow without a
  permissions block, and the backend suite covers those rules.
- **Breaking:** the example secrets are now rejected at startup. The values
  shipped in `docker/.env.example` and `release/.env.example` were accepted, so
  an install that copied an example file and never replaced `JWT_SECRET_KEY` or
  `LOG_INGEST_SHARED_SECRET` ran with a publicly known secret, and anyone could
  mint an admin token. Both files now ship obvious placeholders, the backend
  refuses to start while they are still in place and names the variable to
  replace (`openssl rand -hex 32`), and `make env` creates `docker/.env` from
  the example with generated secrets. Documentation and the smoke workflow use
  `make env` instead of a bare copy. Existing installs must set the two
  variables; nothing else changes, and no data or API is affected.
- The published frontend image serves the built admin UI from nginx instead of
  running the Vite dev server. The UI and the API now share an origin (nginx
  proxies `/api/v1` to the backend and appends the client address to
  `X-Forwarded-For`, which the login rate limit keys on), the container runs as
  an unprivileged user, and every response carries a Content-Security-Policy
  plus nosniff/frame/referrer headers. The host port (`FRONTEND_PORT`, 3000 by
  default) is unchanged; `VITE_DEV_SERVER_PROXY_TARGET` and `VITE_API_BASE_URL`
  are no longer read by the container — run `pnpm dev` in `src/frontend` for
  hot-reload development. **Upgrade note:** the container port moved from 5173
  to 8080, so a Compose file that sets the port mapping itself must use 8080.
- `AUTH_REFRESH_COOKIE_SECURE` keeps its default (false), because the UI is
  served over plain HTTP unless you put it behind TLS, but the backend now logs
  a startup warning while it is false and `release/.env.example` documents
  enabling it once the UI is reached over HTTPS. Without it the long-lived
  refresh cookie travels in clear text.
- The policy editor uses a wider responsive layout with grouped settings and a
  scrollable body; policy actions use the shared green primary button style.
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
- The load test can use a separate client started by hand (`LOAD_CLIENT=manual`):
  for each run the runner prints the `wrk` command, waits for Enter to start
  resource sampling, and reads the pasted wrk output. One setting,
  `LAB_SERVER_ADDR` in `benchmarks/lab/.env` (default `127.0.0.1`), publishes
  Albedo's baseline port (`LAB_FTW_DIRECT_PORT`, 18080) on the server's address
  and gives the wrk URLs. `performance.json` records the mode and both URLs.
- `make eval-sweep` stops at the first failing step and passes the `LOAD_*`
  variables on to the load runner.
- Resource samples record the achieved sampling interval, the sample count
  and the sampled window next to the target interval.
- The evaluation lab pins its remaining images to an exact version and digest —
  WordPress `7.1.3` (`php8.3-apache`), WP CLI `2.12.0-php8.3`, MariaDB
  `11.4.13`, Albedo `0.2.0`, curl `8.11.1`, go-ftw `2.6.0` and wrk `4.2.0` — so
  two runs of the same commit measure the same targets. Each run also records
  the WordPress core version it hit in `manifest.json`. The `version-pins` CI
  job now covers the lab Compose overlay and the runner scripts, and a new
  `benchmarks` CI job runs the lab unit tests.

### Fixed

- A vhost domain is validated as a hostname when it is saved, using the same
  rule the config renderer applies when it writes the host ACL. Before, only
  generation rejected it, so an unusable row could be stored and then blocked
  every config apply until someone corrected it.
- Custom-rule variables and rule-exclusion target values reject a trailing
  newline. The allowlists ended with `$`, which also matches just before a
  trailing newline, so `"ARGS\n"` passed and rendered an extra, broken line
  into the generated Coraza rules — a rule change that fails to compile. Both
  checks are anchored with `\Z` now, at write time and at generation time.
- WAF events no longer keep credentials. The shipper stores the whole Coraza
  audit event as `raw_context` so an event can be investigated, and that event
  includes the request headers, so cookies, `Authorization` values and API keys
  belonging to the protected application's users were written to the database
  and shown in the log viewer to every authenticated user. Values of
  credential-bearing fields — headers named `Cookie`, `Authorization`,
  `X-Api-Key` and similar, or any field matching password/secret/token/
  credential — are replaced with `[redacted]` at ingest. Rule messages, which
  the exclusion suggester parses, are left as they are.
- Login rate limiting can no longer be bypassed by spoofing
  `X-Forwarded-For`. The limiter keyed on the left-most entry of the header,
  but the proxy in front of the backend appends the address it observed instead
  of replacing the header (HAProxy replaces it; the Vite dev server, which is
  also how the release kit publishes the UI, appends), so a client could
  prepend a fresh value to every attempt and never reach the login limit. The
  key is now the right-most entry, the address the closest proxy added, which
  is the same value HAProxy writes; the dev server proxy appends the client
  address (`xfwd`) so the header is never purely client-supplied.
- A WAF payload can no longer forge its own anomaly score. The shipper took the
  first `(Total Score: N)` it found in any audit message, but the request data
  it matched appears inside the message of the rule that matched, so a payload
  containing that text — a query parameter was enough — replaced the real score
  with its own. A value that large overflows the score column, which made
  ingest answer `500` and the shipper retry the same event forever. The score
  is now read only from the CRS blocking-evaluation rule's own message text,
  the ingest schema bounds it to what the column can store, and a store-level
  data error answers `422` (dead-lettered) instead of `500`. HTTP methods
  longer than 16 characters, which the client chooses, and scoped IPv6 client
  addresses no longer make an event unmappable either.
- Unbanning an IP now clears the normalised address and rejects IPv6 scope
  ids (`fe80::1%eth0`). The submitted address was validated but then
  interpolated into the HAProxy Runtime API command as typed, and `ipaddress`
  accepts a scope id containing whitespace or a newline. HAProxy's Runtime API
  executes a single command per connection, so a scope cannot append a second
  command — verified against the pinned HAProxy 3.0.29 — but a scoped or
  non-normalised address produced a confusing Runtime API failure instead of a
  clear `422`.
- Coraza inspects request bodies. HAProxy buffers the request body
  (`option http-buffer-request`, `tune.bufsize 65536`) before the SPOE message
  is built, so a payload written after the headers, or past the first buffer,
  no longer reaches the origin uninspected. The buffer is also the largest
  body Coraza can inspect: coraza-spoa rejects a frame above 64 KiB and fails
  the SPOE handshake, which would answer every request with 503, so
  `tune.bufsize` must stay at or below 65536.
- `/health` skips WAF inspection only while Coraza has no usable server.
  While the WAF is running the path is inspected and counted by the per-vhost
  DDoS limits like any other, so it is no longer an uninspected route to the
  origin; during a WAF outage it still answers, so liveness probes keep
  working. The release kit's demo seed also picks up the slow-loris
  `timeout http-request 5s` it had drifted away from, and a test now keeps
  `release/haproxy/*.cfg` identical to `configs/haproxy/*.cfg`.
- The log shipper fsyncs its offset file, remembers the audit file's device
  and inode, and reads a rotated file to the end before following the new
  file from the start. A corrupt offset is logged and the audit log is read
  again from the start, which is safe because ingest deduplicates retries.
  Lines that cannot be delivered are appended to a dead-letter file next to
  the offset, a Host longer than 255 characters is shortened so ingest does
  not reject it, and a read timeout no longer crashes the shipper. CI runs
  the log-shipper tests.
- `POST /config/apply` no longer reports success when Coraza rejects a rule
  change for a policy that already exists. The Coraza supervisor compiles the
  new release with `coraza-spoa -validate` before it reloads, and writes the
  result under `/runtime/coraza-status/reload-status`. Apply waits for that
  status whenever the Coraza files changed, and restores the previous release
  when compilation fails or the status never arrives. An older Coraza image
  does not write this file: apply then waits for `CORAZA_RELOAD_TIMEOUT_SECONDS`
  and rolls back, so the backend and the `coraza` image have to be updated
  together. The Compose files mount a writable `coraza_status` volume at
  `/runtime/coraza-status` (the rest of `/runtime` stays read-only). A stack
  that keeps an older Compose file still runs, but rule changes fail apply
  until that volume is mounted.
- The image fallback Coraza config no longer declares a
  `default_application`, so an application name it does not define fails the
  SPOE call and HAProxy answers `503` instead of inspecting the request with
  the single baked-in application (paranoia level 1, detect-only). The
  `releases/seed` placeholder — the entrypoint stub, and the demo
  `haproxy.cfg` HAProxy copies into it when nothing has been generated — is no
  longer mistaken for an applied release on a backend restart: it is replaced
  with a rendered release, and a HAProxy that is already running the demo
  config is reloaded onto it. `GET /runtime/status` reports the new
  `active_config` block (`haproxy_source`, `coraza_source`, `degraded`,
  `warning`) and the dashboard shows a warning while the demo seed or the
  Coraza fallback is serving traffic. A release from before per-policy
  applications keeps running on the fallback and is reported as degraded
  until it is applied again.
- Policy editor fields stay on aligned rows when DDoS protection, automatic
  IP banning or country filtering are expanded, and the dashboard's empty
  "Recent blocks" card matches the height of its neighbours.
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

[Unreleased]: https://github.com/bihius/guard-proxy/compare/v0.1.0-beta.6...HEAD
[0.1.0-beta.6]: https://github.com/bihius/guard-proxy/compare/v0.1.0-beta.5...v0.1.0-beta.6
[0.1.0-beta.5]: https://github.com/bihius/guard-proxy/compare/v0.1.0-beta.4...v0.1.0-beta.5
[0.1.0-beta.4]: https://github.com/bihius/guard-proxy/compare/v0.1.0-beta.3...v0.1.0-beta.4
[0.1.0-beta.3]: https://github.com/bihius/guard-proxy/compare/v0.1.0-beta.2...v0.1.0-beta.3
[0.1.0-beta.2]: https://github.com/bihius/guard-proxy/compare/v0.1.0-beta.1...v0.1.0-beta.2
[0.1.0-beta.1]: https://github.com/bihius/guard-proxy/compare/v0.1.0-alpha...v0.1.0-beta.1
[0.1.0-alpha]: https://github.com/bihius/guard-proxy/releases/tag/v0.1.0-alpha
