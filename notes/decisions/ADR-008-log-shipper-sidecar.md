---
date: 2026-05-31
tags: [decision, architecture, logging, m3]
---

# ADR-008: Log Shipper — Custom Python Sidecar over Vector / Fluent Bit

## Context

Coraza already emits one JSON audit event per newline to its audit log, and
the backend already exposes `POST /logs/ingest` (protected by a shared-secret
header) to write events to the `logs` table. The missing piece for M3 is the
component that carries those events from Coraza to the backend — the "log
shipper."

Issue #117 explicitly recommended **Vector** (single binary, low footprint) as
the first choice, with "anything simpler acceptable for MVP." Three off-the-shelf
candidates were evaluated: Vector, Fluent Bit, and a custom Python sidecar.

## Decision

Use a **custom Python sidecar** (`src/log-shipper/`) that tails the Coraza
audit file and POSTs each event individually to `POST /logs/ingest`.

## Rationale

### Why not Vector

Vector's `http` sink always encodes a batch as a **JSON array**. The backend's
ingest endpoint expects a **single JSON object** (the `LogIngestRequest` schema)
and returns `422 Unprocessable Entity` for an array body.

Workarounds all carry unacceptable cost:

| Workaround | Cost |
|---|---|
| Add a batch ingest endpoint | Backend change, new schema, tests |
| `batch.max_events = 1` with `json` codec | Still produces `[{...}]` (array of one) |
| Custom HTTP sink transform / VRL hack | Fragile; not a supported Vector pattern |

Beyond the endpoint-shape mismatch, the Coraza→`LogIngestRequest` field
derivation (derive `action` from `is_interrupted` + per-message severity, bucket
the numeric `severity` into four enum values, coerce string anomaly scores to
int) is already specified as a Python-style mapping table in
`configs/coraza/README.md`. Expressing this in VRL — Vector's transform
language — is significantly more verbose and harder to unit-test.

### Why not Fluent Bit

Fluent Bit is a C binary with Lua scripting for field transforms. Its lower
footprint compared to Vector is irrelevant at this scale; the Lua transform
surface would be the most unfamiliar code in the project for a Python-centric
team.

### Why the custom Python sidecar works well here

1. **Matches the endpoint shape exactly.** One call to `urllib.request.urlopen`
   per event, plain `Content-Type: application/json`, zero wrapper overhead.

2. **Durability via the audit file itself.** The sidecar persists a byte-offset
   checkpoint (on the `shipper_state` volume) and only advances it after a `2xx`
   response or a deliberate skip (parse error or `4xx` rejection). Transient
   failures (`5xx`, network errors, `429`) trigger exponential backoff without
   advancing the offset. The audit file is the buffer — a 30-second backend
   outage stalls the pipeline but loses no events. This is the same checkpointing
   strategy Vector uses for its file source.

3. **Idempotency via `producer_event_id`.** Coraza's `transaction.id` is sent as
   `producer_event_id`; the backend returns `200` for a duplicate, so retried
   lines deduplicate at rest rather than creating double rows.

4. **Stdlib-only runtime.** No dependency management required in the container
   image — `python:3.13-slim` + the `app/` directory is sufficient. All
   complexity lives in a single testable pure function (`mapping.py`).

5. **Language consistency.** The mapping logic and the schema it targets are both
   Python; they can evolve together and share the same test runner (`pytest`).

## Alternatives Considered

### Alternative 1: Vector with `docker_logs` source (Docker socket)

Read Coraza stdout via the Docker API instead of a file. Rejected because:
mounting the Docker socket grants the container broad host-level access — a
security concern that is explicitly out of scope for a WAF-focused thesis project.

### Alternative 2: Vector with shared audit file

Keeps `SecAuditLog /dev/stdout` via `tee` into a file, or changes `SecAuditLog`
to write a file directly (as this ADR does). Vector tails the file via the
`file` source. Still rejected because of the HTTP sink array-wrapping issue
(see above), and because the VRL transform for the mapping is harder to test
and maintain than the equivalent Python.

### Alternative 3: Fluent Bit

Lower binary footprint than Vector. Rejected because: the complex field
derivation (action/severity derivation) would require Lua filter scripting;
the team has no Lua familiarity; and the footprint difference is irrelevant at
this deployment scale.

## Consequences

- `SecAuditLog /dev/stdout` in `configs/coraza/coraza.conf` is changed to
  `/var/log/coraza/audit.log`. Audit JSON is no longer visible in
  `docker logs coraza`; only SPOA operational logs (stderr) appear there.
  The audit file can still be inspected with `docker exec coraza tail -f
  /var/log/coraza/audit.log`.
- A new `coraza_audit` named volume is shared between the `coraza` and
  `log-shipper` containers. A `shipper_state` volume persists the offset.
- The sidecar is a small Python package; it runs as a non-root `shipper` user
  in a `python:3.13-slim` container. Runtime dependencies: none (stdlib only).
- If throughput grows to thousands of events per second in a future milestone,
  the single-event-per-request approach becomes a bottleneck. At that point
  adding a batch ingest endpoint and switching to Vector (or batching in the
  sidecar) is a well-understood migration path.
