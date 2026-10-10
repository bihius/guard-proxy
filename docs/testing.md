# Testing Strategy - Guard Proxy

## Test Pyramid

| Level | Location | Tools | Coverage Goal |
|-------|----------|-------|---------------|
| **Unit** (many, fast) | `src/backend/tests/unit/` | pytest, Vitest | >80% |
| **Integration** (some) | `src/backend/tests/integration/` | pytest, Docker | Key flows |
| **Security** | `benchmarks/lab/` | tagged corpus, go-ftw | Configuration-specific WAF evidence |
| **Performance** | `benchmarks/lab/` | wrk (WAF vs direct) | Latency overhead guardrail: p50 ≤ 10 ms |

## WAF Testing

### Evaluation Metrics

Security metrics are descriptive and configuration-specific. TP/FN/TN/FP are
computed only for the tagged labeled corpus in `benchmarks/payloads/`. go-ftw
reports CRS conformance (share of CRS regression tests whose expected rule IDs
fire or stay silent). The only soft lab guardrail is the p50 latency overhead
(≤ 10 ms) under the documented wrk workload.

### End-to-End Smoke

The M1 smoke test starts the Docker Compose stack, waits for healthy services,
checks that a benign request is allowed, checks that a SQL injection request is
blocked by Coraza, and then tears the stack down.

Prerequisites:

- Docker with Docker Compose
- `docker/.env` created from `docker/.env.example`
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

Full WAF evaluation with two targets: WordPress (`wp.local`, tagged corpus) and
the CRS Albedo backend (`ftw.local`, go-ftw and load test):

```sh
# Prerequisites
cp docker/.env.example docker/.env
cp benchmarks/lab/.env.example benchmarks/lab/.env
git submodule update --init --recursive

# Ensure docker/.env has ADMIN_EMAIL and ADMIN_PASSWORD set.

# Bring up the lab
make eval-up

# Run all three tests (corpus → ftw → load → metrics)
make eval-all

# View results
make eval-results
```

See `benchmarks/lab/` for scenario configs and `docs/evaluation-plan.md` for methodology.

## Test Data

- Payloads: `benchmarks/payloads/` (sqli.txt, xss.txt, lfi.txt, legitimate.txt)
- Results: `benchmarks/results/` (timestamped JSON/CSV, gitignored)

## Commands

See [commands.md](commands.md) for all test commands.

For frontend work, use `pnpm` as the only package manager.
