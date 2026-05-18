# Testing Strategy - Guard Proxy

## Test Pyramid

| Level | Location | Tools | Coverage Goal |
|-------|----------|-------|---------------|
| **Unit** (many, fast) | `src/backend/tests/unit/` | pytest, Vitest | >80% |
| **Integration** (some) | `src/backend/tests/integration/` | pytest, Docker | Key flows |
| **Security** | `tests/security/` | sqlmap, OWASP ZAP, custom payloads | OWASP Top 10 |
| **Performance** | `benchmarks/` | wrk, k6, Locust | <20% WAF overhead |

## WAF Testing

### Detection Targets (draft)
- SQL Injection: >95% detection rate
- XSS: >95% detection rate
- Path Traversal: >95% detection rate
- False positive rate: <10%

### End-to-End Smoke

The M1 smoke test starts the Docker Compose stack, waits for healthy services,
checks that a benign request is allowed, checks that a SQL injection request is
blocked by Coraza, and then tears the stack down.

Prerequisites:

- Docker with Docker Compose
- `deploy/docker/.env` created from `deploy/docker/.env.example`
- The CRS submodule initialised with `git submodule update --init --recursive`

Run locally:

```sh
bash benchmarks/smoke/e2e.sh
```

The smoke test sends `Host: app.local` because the reference HAProxy
configuration rejects unknown hosts before WAF inspection. The same smoke test
also runs nightly and on demand through `.github/workflows/smoke.yml`.

### Policy Apply E2E

The policy apply e2e test starts an isolated Compose project, seeds an admin,
creates a policy-backed `app.local` vhost, applies runtime config, and verifies
that disabling and re-enabling CRS rule `913100` changes live request behavior.

Run locally from the backend directory:

```sh
uv run pytest -m e2e tests/e2e/test_policy_apply.py
```

The test uses the same prerequisites as the smoke test and is wired into the
nightly smoke workflow. Normal backend pytest runs exclude tests marked `e2e`.

## Test Data

- Payloads: `benchmarks/payloads/` (sqli.txt, xss.txt, legitimate.txt)
- Results: `benchmarks/results/` (timestamped JSON, gitignored)

## Commands

See [README.commands.md](README.commands.md) for all test commands.

For frontend work, use `pnpm` as the only package manager.
