# Coraza configuration

This directory contains the static Coraza SPOA and OWASP CRS bundle. The
per-policy parts (CRS setup and tuning of each Coraza application) are
generated from the policy database on every config apply; see
`docs/architecture.md` (Policy Management).

## First-time setup

The `crs/` directory is a git submodule. If you cloned the repository without
`--recurse-submodules` (or your CI checkout did not initialise submodules), run:

```sh
git submodule update --init --recursive
```

## Pinned versions

- Coraza SPOA image: `ghcr.io/corazawaf/coraza-spoa:0.6.1`, pinned by digest
  in `docker/coraza.Dockerfile`
- OWASP Core Rule Set: `v4.25.0`, pinned as the `configs/coraza/crs` git
  submodule

See "Pinned component versions" in `docs/architecture.md` for every pinned
image and how to bump them.

## Files

| File | Purpose |
| --- | --- |
| `coraza-spoa.yaml` | Fallback single-application daemon config, used only while the active release has no generated `coraza-spoa.yaml` (one application per policy) |
| `coraza.conf` | Baseline directives (audit log, body access, JSON/XML body processors) included first by every application |
| `crs-setup.conf` | Reference CRS setup; the generated per-policy `crs-setup.conf` is compared against it in tests |
| `crs/` | Pinned OWASP CRS 4.x submodule |
| `guard-proxy-exceptions.conf` | Guard Proxy-owned CRS false-positive exceptions, loaded after CRS rules. Not part of the `crs/` submodule, so it survives CRS version bumps. |

## Defaults

- Request inspection is enabled with `SecRuleEngine On`.
- Response body inspection is disabled for M1, matching ADR-007.
- Blocking paranoia level is `1`.
- Inbound and outbound anomaly thresholds are `5`.

### Why a single PL1 rule can block a request at the default threshold

CRS scores each fired rule by severity and sums the scores per transaction
into `tx.inbound_anomaly_score`. A request is blocked once that sum reaches
`inbound_anomaly_threshold`. Severity → score: `critical` = 5, `error` = 4,
`warning` = 3, `notice` = 2. At the default threshold of `5`, **one single
`critical`-severity PL1 rule match is enough to block the request by
itself** — there's no need for multiple rules to combine.

This is exactly what happened with a real plain WordPress site
(`wp.bihius.me`) under the default policy (`paranoia_level=1`,
`inbound_anomaly_threshold=5`): rule **942290** ("Finds basic MongoDB SQL
injection attempts", PL1, `critical` severity = score 5) fired on every
request because the browser sent a PostHog analytics cookie
(`ph_phc_<project_key>_posthog`) whose JSON value contains `$`-prefixed keys
like `"$initialization_time"` — the literal substring `$in` collides with
942290's MongoDB `$in` operator heuristic. One critical false positive ==
threshold 5 → the request was denied (403), even though nothing in the
request was attacker-controlled.

This is a known false-positive class — CRS already ships built-in exclusions
for the same pattern with Google Analytics/Ads cookies (`_ga`, `__gads`, see
`crs/rules/REQUEST-999-COMMON-EXCEPTIONS-AFTER.conf`). The fix here follows
the same approach for the PostHog cookie via `guard-proxy-exceptions.conf`
(see the Files table above) rather than lowering the global anomaly
threshold, which would weaken protection against real SQL/NoSQL injection
attempts site-wide. Operators hitting similar noisy false positives from
other third-party cookies/headers can add the same
`SecRuleUpdateTargetById <rule> "!REQUEST_COOKIES:/pattern/"` pattern to that
file, or raise `inbound_anomaly_threshold` for a specific noisy policy via
the Policies UI as a coarser, per-vhost workaround.

## Audit log output

Coraza writes one JSON audit event per line to
**`/var/log/coraza/audit.log`** (on the `coraza_audit` Docker named volume)
using `SecAuditLogType Serial` + `SecAuditLogFormat JSON`. Each transaction
that matches `SecAuditEngine RelevantOnly` (i.e. transactions where at least
one rule fired) produces a single JSON object followed by a newline.

Operational logs from the `coraza-spoa` daemon (startup, health, rule-load
messages) continue to go to **stderr** and appear in `docker logs coraza`.

To inspect audit events while the stack is running:

```sh
# tail the audit file inside the container
docker compose -f docker/docker-compose.yml --env-file docker/.env \
  exec coraza tail -f /var/log/coraza/audit.log | jq -c .

# SPOA operational logs (stderr)
docker compose -f docker/docker-compose.yml --env-file docker/.env \
  logs --no-log-prefix coraza
```

The log-shipper sidecar (`src/log-shipper/`) tails this file and ships each
event to `POST /logs/ingest` on the backend. The supervisor truncates the file
in place once it grows past `CORAZA_AUDIT_LOG_MAX_BYTES` (default 256 MiB,
`audit.log.1` keeps one backup): Coraza holds the file open, so a rename would
leave it writing to the renamed file while the new one stays empty, and the
database — not this file — is the archive. The shipper notices the truncation
and reads the file from the start again. See `docs/architecture.md` for the full
data-flow description.

### Event schema and ingest mapping

The Coraza audit event and the `LogIngestRequest` payload are both JSON, but
they do not have the same schema. Coraza uses a nested transaction-oriented
structure, while the backend expects a flat, validated API object. The
log-shipper translates between them in `src/log-shipper/app/mapping.py`.

The documented audit-log parts `ABIJDEFHZ` describe a structure like:

```jsonc
{
  "transaction": {
    "id": "...",
    "timestamp": "2026/05/31 13:29:17",
    "client_ip": "...",
    "is_interrupted": false,
    "request": {
      "method": "GET",
      "uri": "/path",
      "headers": { "host": ["example.com"], ... }
    }
  },
  "messages": [
    {
      "error_message": "[id \"941100\"] [msg \"XSS Attack Detected\"] [severity \"critical\"]"
    }
  ]
}
```

In the actual `coraza-spoa:0.6.1` output, `messages[].data` is `null`,
`transaction.variables` is absent, and the timestamp has no timezone. The
shipper treats this timestamp as UTC, parses rule fields from
`messages[].error_message`, and keeps compatibility with a future structured
`messages[].data` object if Coraza starts populating it.

| `LogIngestRequest` field | Coraza source path | Notes |
|---|---|---|
| `producer_event_id` | `transaction.id` | Unique per transaction |
| `event_at` | `transaction.timestamp` | Parses ISO 8601, Coraza's `YYYY/MM/DD HH:MM:SS`, or Apache-style timestamp; missing timezone means UTC |
| `vhost` | `transaction.request.headers.host` | First header value; normalized to lowercase and stripped of port; `unknown` if unavailable |
| `source_ip` | `transaction.client_ip` | Must be a valid IP address; otherwise the event is skipped |
| `method` | `transaction.request.method` | Uppercase |
| `request_uri` | `transaction.request.uri` | |
| `status_code` | `transaction.response.status` | May be absent for blocked requests |
| `action` | derived | `deny` if `transaction.is_interrupted`; `monitor` if not interrupted but a CRS blocking-evaluation rule (949110, 949111, 959100, 959101) matched, i.e. a DetectionOnly policy reached its threshold; when `is_interrupted` is absent, `deny` if the first rule's severity is emergency/alert/critical; else `allow` |
| `rule_id` | first rule-bearing `messages[].data.id` or parsed `messages[].error_message` | One row is stored for one transaction |
| `rule_message` | first rule-bearing `messages[].data.msg` or parsed `messages[].error_message` | Corresponds to `rule_id` |
| `anomaly_score` | `transaction.variables.tx.anomaly_score`, otherwise parsed from the CRS blocking message | String → integer; `null` when unavailable |
| `paranoia_level` | `transaction.variables.tx.paranoia_level` | String → integer; normally unavailable in `coraza-spoa:0.6.1` |
| `severity` | not sent by the shipper; the backend derives it at ingest | `high` if `anomaly_score` >= 2x the resolved policy's `inbound_anomaly_threshold`; `medium` if the request was denied or monitored, or the score reached the threshold; else `low`. Vhosts without a policy use the default threshold `5` |
| `message` | — | Always `null`; reserved for a future non-Coraza producer |
| `raw_context` | full Coraza event JSON | Preserves unmapped details, including all matched rules |

### Known gaps in the mapped fields

- **`paranoia_level`** — `coraza-spoa:0.6.1` doesn't expose `tx.*` variables to
  the SPOA response, so `transaction.variables.tx.paranoia_level` is never
  present and the shipper always sends `null`. The backend backfills it at
  ingest time from the resolved vhost's policy (`paranoia_level` column on
  `policies`), so `GET /logs` reports the *effective* paranoia level even
  though the shipper itself can't observe it.
- **`message`** (the `LogIngestRequest.message` field, distinct from
  `rule_message`) — the shipper never populates it; it always ships as `null`.
  There is no separate event-level message in Coraza beyond the per-rule
  message already captured as `rule_message`. Treat `message` as reserved for
  a future non-Coraza log producer rather than a bug to fix.
- **`status_code`** — absent for requests Coraza interrupts (blocked/denied
  before reaching the upstream), since there is no upstream response to read
  a status from. A blank status code in the log viewer for a `deny` event is
  expected, not a missing-data bug.

## Docker Compose mounts

When the stack runs through `docker/docker-compose.yml`, these files are
mounted into the Coraza container read-only. After editing files in this
directory, restart the service so `coraza-spoa` reloads them:

```sh
docker compose -f docker/docker-compose.yml --env-file docker/.env restart coraza
```

The Coraza image still ships the same defaults, so it can run outside the
compose stack without host-mounted configuration.

## Updating CRS

```sh
git -C configs/coraza/crs fetch --tags
git -C configs/coraza/crs checkout v4.x.y
```

After updating, also change the pinned CRS version in
`docker/coraza.Dockerfile`, `configs/coraza/crs-setup.conf`, and this
README.
