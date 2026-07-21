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

```bash
make eval-up       # Start demo stack + lab targets
make eval-ftw      # CRS go-ftw conformance against ftw.local
make eval-corpus   # Tagged labeled corpus for TP/FN/TN/FP
make eval-zap      # Supplemental ZAP scanner report
make eval-nuclei   # Supplemental Nuclei reached-app findings
make eval-load     # wrk RPS/latency overhead
make eval-all      # ftw → corpus → zap → nuclei → load → metrics
make eval-results  # Show latest CSV summary
```

## Performance Testing

```bash
wrk -t4 -c100 -d30s --latency http://localhost:8080/test  # HTTP benchmark
make eval-load                                              # RPS/latency overhead vs. direct backend
```
