# Testing Strategy - Guard Proxy

## Test Pyramid

| Level | Location | Tools | Coverage Goal |
|-------|----------|-------|---------------|
| **Unit** (many, fast) | `src/backend/tests/unit/` | pytest, Vitest | >80% |
| **Integration** (some) | `src/backend/tests/integration/` | pytest, Docker | Key flows |
| **Security** | `benchmarks/lab/` | OWASP ZAP, Nuclei, go-ftw (CRS corpus) | OWASP Top 10 |
| **Performance** | `benchmarks/lab/` | wrk (WAF vs direct) | <20% WAF overhead |

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

## Evaluation Lab (thesis M6)

Full WAF evaluation with real target apps (WordPress, Juice Shop, DVWA):

```sh
# Prerequisites
cp deploy/demo/.env.example deploy/demo/.env
cp benchmarks/lab/.env.example benchmarks/lab/.env
git submodule update --init --recursive

# Bring up the lab
make eval-up

# Run all scenarios (ftw → zap → nuclei → load → metrics)
make eval-all

# View results
make eval-results
```

See `benchmarks/lab/` for scenario configs and `docs/evaluation-plan.md` for methodology.

## Test Data

- Payloads: `benchmarks/payloads/` (sqli.txt, xss.txt, lfi.txt, legitimate.txt)
- Results: `benchmarks/results/` (timestamped JSON/CSV, gitignored)

## Commands

See [README.commands.md](README.commands.md) for all test commands.

For frontend work, use `pnpm` as the only package manager.
