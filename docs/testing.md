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

Full WAF evaluation with two targets — WordPress (`wp.local`) and the CRS
Albedo backend (`ftw.local`) — and three tests:

| Test | What                                                        | Runs on     | Target      |
| ---- | ----------------------------------------------------------- | ----------- | ----------- |
| 1    | Tagged corpus: 39 benign + 50 attacks × (GET `?s=`, POST comment form) = 139 cases | lab server (curl) | `wp.local` |
| 2    | CRS regression suite, go-ftw in log mode (rule IDs checked) | lab server  | `ftw.local` |
| 3    | wrk load, WAF vs direct, 8 GET + 2 POST mix                 | load client | `ftw.local` |

Both PL1 and PL2 run in one command; the profiles differ only in paranoia level
(thresholds 5/4, block mode, no exclusions, rate limiting and GeoIP off). On
the lab server, with `wrk` started by hand on the load client:

```sh
# Prerequisites
cp docker/.env.example docker/.env               # must set ADMIN_EMAIL and ADMIN_PASSWORD
cp benchmarks/lab/.env.example benchmarks/lab/.env   # set LAB_SERVER_ADDR=10.99.99.20
git submodule update --init --recursive

make -C benchmarks lab-up
make -C benchmarks eval-sweep RUN_ID=<id> LOAD_CLIENT=manual
```

With `LOAD_CLIENT=manual` the sweep pauses at each wrk run, prints the command
for the client, and waits for its output to be pasted back. Without
`LOAD_CLIENT=manual` (and with `LAB_SERVER_ADDR=127.0.0.1`) everything runs on one
machine, which is enough for a smoke run. See
[commands.md](commands.md#evaluation-lab) for the variables and
[evaluation-plan.md](evaluation-plan.md) for methodology. Keep demo traffic
generation off during measurements.

Unit tests for the metric parsers: `cd benchmarks && python -m pytest tests`.

## Test Data

- Payloads: `benchmarks/payloads/` (sqli.txt, xss.txt, lfi.txt, legitimate.txt)
- Results: `benchmarks/results/` (timestamped JSON/CSV, gitignored)

## Commands

See [commands.md](commands.md) for all test commands.

For frontend work, use `pnpm` as the only package manager.
