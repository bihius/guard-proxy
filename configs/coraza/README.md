# Coraza configuration

This directory contains the hand-written M1 Coraza SPOA and OWASP CRS bundle.
M2 will replace these seed files with generated configuration derived from the
policy database.

## First-time setup

The `crs/` directory is a git submodule. If you cloned the repository without
`--recurse-submodules` (or your CI checkout did not initialise submodules), run:

```sh
git submodule update --init --recursive
```

## Pinned versions

- Coraza SPOA image: `ghcr.io/corazawaf/coraza-spoa:0.6.1`
- OWASP Core Rule Set: `v4.25.0`, pinned as the `configs/coraza/crs` git
  submodule

## Files

| File | Purpose |
| --- | --- |
| `coraza-spoa.yaml` | `coraza-spoa` daemon configuration and default application mapping |
| `coraza.conf` | Baseline Coraza directives and CRS includes |
| `crs-setup.conf` | CRS paranoia and anomaly-scoring defaults |
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
event to `POST /logs/ingest` on the backend. See `README.architecture.md` for
the full data-flow description.

### Event schema and ingest mapping

The table below maps each `LogIngestRequest` field (defined in
`src/backend/app/schemas/log.py`) to its source path inside the Coraza JSON
event. The mapping is implemented in `src/log-shipper/app/mapping.py`.

Parts `ABIJDEFHZ` produce a top-level structure like:

```jsonc
{
  "transaction": {
    "id": "...",
    "timestamp": "...",
    "client_ip": "...",
    "is_interrupted": false,
    "request": {
      "method": "GET",
      "uri": "/path",
      "headers": { "host": "example.com", ... }
    },
    "response": { "status": 200 },
    "variables": {
      "tx": {
        "anomaly_score": "5",
        "paranoia_level": "1"
      }
    }
  },
  "messages": [
    {
      "message": "...",
      "data": { "id": "941100", "msg": "XSS Attack ...", "severity": "2" }
    }
  ]
}
```

| `LogIngestRequest` field | Coraza source path | Notes |
|---|---|---|
| `producer_event_id` | `transaction.id` | Unique per transaction |
| `event_at` | `transaction.timestamp` | ISO 8601 string |
| `vhost` | `transaction.request.headers.host` | Lowercase |
| `source_ip` | `transaction.client_ip` | |
| `method` | `transaction.request.method` | Uppercase |
| `request_uri` | `transaction.request.uri` | |
| `status_code` | `transaction.response.status` | May be absent for blocked requests |
| `action` | derived | `deny` if `transaction.is_interrupted` or any `messages[].data.severity` < 2; `monitor` when `SecRuleEngine DetectionOnly`; else `allow` |
| `rule_id` | `messages[0].data.id` | First (or highest-severity) fired rule |
| `rule_message` | `messages[0].data.msg` | Corresponding rule message |
| `anomaly_score` | `transaction.variables.tx.anomaly_score` | String → int; absent when no rules fired |
| `paranoia_level` | `transaction.variables.tx.paranoia_level` | String → int |
| `severity` | derived from `messages[0].data.severity` | Numeric Coraza severity: 0–2 → `critical`/`error`; 3–4 → `warning`; ≥5 → `info` |
| `raw_context` | full Coraza event JSON | Fallback; stores everything not mapped above |

### Known gaps in the mapped fields

- **`paranoia_level`** — `coraza-spoa:0.6.1` doesn't expose `tx.*` variables to
  the SPOA response, so `transaction.variables.tx.paranoia_level` is never
  present and the shipper always sends `null`. The backend backfills it at
  ingest time from the resolved vhost's policy (`paranoia_level` column on
  `policies`), so `GET /logs` reports the *effective* paranoia level even
  though the shipper itself can't observe it.
- **`message`** (the `LogIngestRequest.message` field, distinct from
  `rule_message`) — the shipper never populates it; it always ships as
  `null`. There is no separate "message" concept in a Coraza event beyond the
  per-rule `messages[].data.msg` already captured as `rule_message`. Treat
  `message` as reserved for a future non-Coraza log producer rather than a
  bug to fix.
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
