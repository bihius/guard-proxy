# Development Commands - Guard Proxy

> Single source of truth for all development commands.

## Python (Backend)

```bash
# Tests
pytest                                     # Run all tests
pytest --cov=app --cov-report=term-missing # With coverage
pytest tests/unit/                         # Unit tests only
pytest tests/integration/                  # Integration tests only
pytest -k "sqli"                           # Tests matching pattern
pytest -x -v                               # Stop on first failure, verbose

# Type checking & linting
mypy app/
ruff check app/
ruff format app/
```

## Database (Alembic)

```bash
uv run alembic -c src/backend/alembic.ini upgrade heads                          # Apply all migrations (CI smoke test on fresh SQLite)
uv run alembic -c src/backend/alembic.ini check                                  # Fail when models drift from the latest migration
uv run alembic -c src/backend/alembic.ini revision --autogenerate -m "message"  # Generate a migration for model changes
```

## TypeScript (Frontend)

```bash
pnpm install          # Install frontend dependencies
pnpm test             # Run tests
pnpm run type-check   # TypeScript compiler check
pnpm run lint         # ESLint
pnpm run format       # Prettier
pnpm run build        # Production build
pnpm run dev          # Dev server (port 3000)
```

## HAProxy

```bash
haproxy -c -f configs/haproxy/haproxy.cfg  # Validate config
systemctl reload haproxy                    # Graceful reload (NEVER restart in prod)
docker-compose -f docker/docker-compose.yml --env-file docker/.env exec haproxy tcpdump -i any -A -s 0 port 9000  # Debug SPOE traffic (inside container)
```

## Docker

```bash
cp docker/.env.example docker/.env                     # Create env file for compose
docker-compose -f docker/docker-compose.yml --env-file docker/.env config
make run                                                             # Start all services (normal mode)
make dev                                                             # Start all services with HAProxy -d flag and Coraza debug logging
make coraza-build                                                    # Build the pinned Coraza SPOA + CRS image
docker-compose -f docker/docker-compose.yml --env-file docker/.env restart coraza  # Reload mounted Coraza config/rules
docker volume ls | grep guard_proxy                                  # Inspect pgdata, log, and guard_proxy_runtime volumes
make ps                                                              # Show service status
make logs                                                            # Follow all service logs
make down                                                            # Stop stack (keeps named volumes)
make clean                                                           # Stop stack and remove volumes
make seed                                                            # Seed admin user in backend container
```

## User Management

There is no REST endpoint for managing users; accounts are managed with the
backend CLI (run inside the backend container via `./bin/users`).

```bash
# Bootstrap the first admin (idempotent; reads ADMIN_EMAIL / ADMIN_PASSWORD
# from docker/.env when --email/--password are omitted)
make seed

# Manage further accounts with the manage_users.py CLI
./bin/users create --email alice@example.com --password '<min 12 chars>' --full-name 'Alice' --role viewer
./bin/users list                                # All users (add --json for JSON output)
./bin/users list --role admin --active          # Filtered list
./bin/users update alice@example.com --role admin  # Promote by email
./bin/users update 3 --deactivate               # Deactivate by user ID
./bin/users update 3 --password '<new password>'   # Reset a password
./bin/users --help
```

Outside Docker (local backend checkout):

```bash
cd src/backend
uv run python scripts/seed_admin.py --email admin@example.com --password '<min 12 chars>'
uv run python scripts/manage_users.py --help
```

## Smoke Testing

```bash
bash benchmarks/smoke/e2e.sh  # Compose stack: benign request returns 200, SQLi returns 403
cd src/backend && uv run pytest -m e2e tests/e2e/test_policy_apply.py  # Policy apply changes live WAF behavior
```

## Security Testing

```bash
sqlmap -u "http://localhost:8080/test?id=1" --batch   # SQL injection
zap-cli quick-scan -s all http://localhost:8080        # OWASP ZAP
```

## Evaluation Lab

The lab runs on two hosts connected directly by an Ethernet cable: the lab
server (`LAB_SERVER_ADDR` in `benchmarks/lab/.env`, thesis lab `192.168.2.5`)
runs the stack, both targets, the curl corpus and go-ftw; the load client
(thesis lab `192.168.2.1`) runs only native `wrk`. See
[evaluation-plan.md](evaluation-plan.md) for the methodology.

```bash
# On the lab server, once:
git submodule update --init --recursive          # CRS v4.25.0
cp docker/.env.example docker/.env
cp benchmarks/lab/.env.example benchmarks/lab/.env
# In benchmarks/lab/.env set the server's address on the client link:
#   LAB_SERVER_ADDR=192.168.2.5

# Full evaluation: PL1 then PL2, all three tests each, wrk started by hand on the load client
make -C benchmarks lab-up
make -C benchmarks eval-sweep RUN_ID=<id> LOAD_CLIENT=manual
```

`eval-sweep` writes results to `benchmarks/results/run-<id>-pl1/` and
`run-<id>-pl2/`. Without `LOAD_CLIENT=manual` it runs `wrk` in a container on
the same machine (smoke runs only).

Single steps (`POLICY=pl1|pl2`, default `pl1`):

```bash
make -C benchmarks set-policy POLICY=pl2  # write the profile into both lab policies
make -C benchmarks eval-corpus            # Test 1: 139-case corpus on wp.local (TP/FN/TN/FP)
make -C benchmarks eval-ftw               # Test 2: CRS regression suite (go-ftw, log mode) on ftw.local
make -C benchmarks eval-load              # Test 3: wrk RPS/latency overhead on ftw.local (WAF vs direct)
make -C benchmarks eval-all               # corpus → ftw → load → metrics
make -C benchmarks results RUN_ID=<id> POLICY=pl2
```

Load-client variables (also accepted by `eval-all` and `eval-sweep`):

| Variable           | Meaning                                                                 |
| ------------------ | ----------------------------------------------------------------------- |
| `LOAD_CLIENT`      | `manual`: wrk is started by hand on a separate client (default `local`: container on the server) |
| `LOAD_THREADS`, `LOAD_CONNECTIONS`, `LOAD_DURATION` | wrk settings (default 2, 20, 30s)      |

With `LOAD_CLIENT=manual`, every load test pauses twice (WAF run, then direct
run). For each run the server prints the exact `wrk` command. On the client
(a checkout of the same commit, `brew install wrk`), run it from the repository
root; press Enter on the server when you start it, so that resource sampling
covers the WAF run. When wrk finishes, paste its whole output into the server
terminal; reading stops at the `WRK_SUMMARY` line. Nothing connects to the
client. The measured HTTP goes from the client to `LAB_SERVER_ADDR` over the
direct cable for both paths: HAProxy on `HAPROXY_HTTP_PORT`, Albedo directly on
`LAB_FTW_DIRECT_PORT` (18080), which is published only on `LAB_SERVER_ADDR`.
Set it back to `127.0.0.1` and restart the lab after the evaluation. Do not
run other load on either host during a measurement.

## Performance Testing

```bash
wrk -t4 -c100 -d30s --latency http://localhost:8080/test  # HTTP benchmark
make -C benchmarks eval-load                               # RPS/latency overhead vs. direct backend
```
