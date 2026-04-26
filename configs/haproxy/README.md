# HAProxy reference configuration

This directory contains the hand-written reference configuration that
HAProxy uses to consult the Coraza SPOA WAF. It is intentionally small
and readable: M2 (#110) will replace it with Jinja2 templates rendered
from the policy database, so this file is the seed those templates
must reproduce.

## Files

| File         | Purpose                                                  |
|--------------|----------------------------------------------------------|
| `haproxy.cfg`| Frontend, vhost ACL, SPOE filter, backends               |
| `coraza.cfg` | SPOE engine + message definition for the Coraza SPOA    |
| `README.md`  | This document                                            |

## Request flow

```
Client ──► HAProxy :80 ──► (SPOE) ──► Coraza SPOA :9000
                ▲                          │
                │                          ▼
                └──── allow / deny ◄── decision
                │
                ▼ (if allowed)
            Backend  app.local ──► be_app (backend:8000)
```

1. The client sends an HTTP request to HAProxy on port 80.
2. The `fe_http` frontend stamps it with `X-Request-ID` and matches
   the `Host` header against the `host_app` ACL. Anything that is not
   `app.local` is rejected with `421 Misdirected Request`.
3. The `spoe` filter sends a `coraza-req` message to the
   `coraza-spoa` backend (TCP, `coraza:9000`).
4. The SPOA evaluates the request against Coraza/CRS rules and
   returns variables under `txn.coraza.*`.
5. If `txn.coraza.action == "deny"`, HAProxy responds with
   `403 Forbidden` and never contacts the backend.
6. Otherwise the request is routed to `be_app`, which forwards to
   `backend:8000` (the FastAPI service in Docker Compose).

## SPOE variables

All variables set by the SPOA are namespaced via
`option var-prefix coraza`, so HAProxy sees them as `txn.coraza.<name>`.

| Variable             | Meaning                                                |
|----------------------|--------------------------------------------------------|
| `txn.coraza.action`  | Decision string (`deny` blocks; anything else allows)  |
| `txn.coraza.anomaly_score` | Inbound anomaly score from the rule set, propagated as header |
| `txn.coraza.id`      | Transaction id correlated with HAProxy's `unique-id`  |

The exact set of variables produced depends on the Coraza SPOA
version and rule configuration; the three above are the minimum this
reference relies on.

## SPOE message arguments

`coraza-req` is sent by the `coraza-req` SPOE group and carries the data
Coraza needs to run request-phase rules:

| Argument   | HAProxy fetch    | Notes                                  |
|------------|------------------|----------------------------------------|
| `app`      | `str(default)`   | Which Coraza application bundle to use |
| `id`       | `unique-id`      | Same value as the `X-Request-ID` header|
| `src-ip`   | `src`            | Client IP                              |
| `src-port` | `src_port`       | Client TCP port                        |
| `dst-ip`   | `dst`            | HAProxy bind IP                        |
| `dst-port` | `dst_port`       | HAProxy bind port                      |
| `method`   | `method`         | HTTP method                            |
| `path`     | `path`           | Request path without query             |
| `query`    | `query`          | Raw query string                       |
| `version`  | `req.ver`        | HTTP version                           |
| `headers`  | `req.hdrs`       | All request headers, framed for SPOE   |
| `body`     | `req.body`       | Request body (subject to SPOA limits)  |
| `exportRuleIDs` | `bool(false)` | Keep rule-id export disabled by default |

Response-phase inspection is deliberately out of scope for M1
(see ADR-007).

## Degraded-mode behaviour

`spoe-agent` is configured with `option set-on-error error`. If the
SPOA is unreachable, times out, returns a malformed response, or
returns an internal processing error, HAProxy sets
`txn.coraza.error` to the SPOE/SPOP error code.

The M1 reference configuration fails closed for protected traffic:
when `txn.coraza.error` is present, HAProxy returns
`503 Service Unavailable` before contacting `be_app`. The response
includes `X-WAF-Degraded: true` and `X-WAF-Error: <code>` so operators
can distinguish WAF degraded mode from an application outage. HAProxy
also raises the request log level to `err` for these requests.

This covers startup or unhealthy Coraza containers, connection
failures, SPOE processing timeouts, malformed WAF responses, and
transient runtime failures. Backend/dashboard status reporting is
tracked separately in #69.

## Troubleshooting SPOE frames

The M1 reference stack supports an opt-in debug mode (`make dev`) that runs
HAProxy with the `-d` flag and switches Coraza SPOA logging to `debug` level,
so a single request can be followed across both services. The default `make run`
mode uses `info` logging.

> **Warning:** debug mode logs full request metadata. Use only for local
> troubleshooting against non-production traffic.

1. Start the stack in debug mode and follow only the WAF path logs:

   ```sh
   make dev
   docker-compose -f deploy/docker/docker-compose.yml --env-file deploy/docker/.env logs -f haproxy coraza
   ```

2. Send a request with an explicit correlation id:

   ```sh
   curl -i \
     -H "Host: app.local" \
     -H "X-Request-ID: spoe-debug-1" \
     "http://localhost:8080/?id=1%27%20OR%20%271%27=%271"
   ```

3. Check HAProxy output first:

   - the request should pass through `fe_http`;
   - non-`/health` requests should trigger `send-spoe-group coraza coraza-req`;
   - denied requests should show a `403` generated before `be_app`;
   - allowed requests with a score should include the `X-WAF-Score` header.

4. Check Coraza output next:

   - the SPOA should receive the `default` application name;
   - request metadata should match the `coraza-req` arguments documented above;
   - matching CRS rules should also appear in `/var/log/coraza/audit.json`.

5. If HAProxy returns `421`, the request failed the reference host ACL
   before routing. Retry with `Host: app.local`.

6. If HAProxy returns `503` with `X-WAF-Degraded: true`, Coraza/SPOA
   inspection failed and the proxy failed closed before contacting the
   backend. Use the `X-WAF-Error` value and HAProxy `err` log line to
   identify the SPOE/SPOP failure class.

For raw frame inspection in the Docker Compose setup, capture the SPOA
traffic from inside the `haproxy` container while reproducing the
request. Container-to-container traffic does not normally traverse the
host `lo` interface:

```sh
docker-compose -f deploy/docker/docker-compose.yml --env-file deploy/docker/.env \
  exec haproxy tcpdump -i any -A -s 0 port 9000
```

## Validating the config

The configuration is exercised in two ways:

1. Syntax / semantic check (no runtime needed):

   ```sh
   haproxy -c -f configs/haproxy/haproxy.cfg
   ```

   If `haproxy` is not installed locally, run the same check inside
   the pinned image:

   ```sh
   docker run --rm \
     -v "$PWD/configs/haproxy:/usr/local/etc/haproxy:ro" \
     haproxy:3.0-alpine \
     haproxy -c -f /usr/local/etc/haproxy/haproxy.cfg
   ```

   The check must report `Configuration file is valid` with no
   warnings.

2. End-to-end smoke test against the full Docker Compose stack:

   ```sh
   docker-compose -f deploy/docker/docker-compose.yml --env-file deploy/docker/.env up -d --build
   docker-compose -f deploy/docker/docker-compose.yml --env-file deploy/docker/.env ps
   curl -i http://localhost:8080/health
   curl -i "http://localhost:8080/?id=1%27%20OR%20%271%27=%271"
   docker-compose -f deploy/docker/docker-compose.yml --env-file deploy/docker/.env down
   ```

   All five services should become healthy. The benign `/health` request
   should return `200 OK`; the SQL-injection payload should return
   `403 Forbidden`. The backend currently does not define a root route, so
   `/` returns `404 Not Found` even though it is routed through HAProxy.

## Relationship to other issues

- ADR-007 — picks upstream `coraza-spoa` as the SPOA implementation.
- #106 — provides the Coraza SPOA + OWASP CRS bundle this config
  talks to.
- #107 — wires this `configs/haproxy/` directory into Docker Compose.
- #108 — runs the end-to-end smoke test that this reference unblocks.
- #110 — replaces these files with Jinja2 templates seeded from this
  reference.
