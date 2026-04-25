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
tcpdump -i lo -A -s 0 port 9000            # Debug SPOE traffic
```

## Docker

```bash
cp deploy/docker/.env.example deploy/docker/.env                     # Create env file for compose
docker-compose -f deploy/docker/docker-compose.yml --env-file deploy/docker/.env config
make dev                                                             # Start all services (attached, with build)
make coraza-build                                                    # Build the pinned Coraza SPOA + CRS image
make ps                                                              # Show service status
make logs                                                            # Follow all service logs
make down                                                            # Stop stack and remove volumes
make seed                                                            # Seed admin user in backend container
```

## Security Testing

```bash
sqlmap -u "http://localhost:8080/test?id=1" --batch   # SQL injection
zap-cli quick-scan -s all http://localhost:8080        # OWASP ZAP
```

## Performance Testing

```bash
wrk -t4 -c100 -d30s --latency http://localhost:8080/test  # HTTP benchmark
k6 run benchmarks/scripts/k6_test.js                       # Load testing
```
