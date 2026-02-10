---
date: 2026-02-07
tags: [decision, architecture, database]
---

# ADR-002: PostgreSQL for Production, SQLite for Development

## Context
The policy management panel needs persistent storage for:
- Virtual host configurations (domain, backend URL, SSL settings)
- WAF policies (paranoia level, anomaly thresholds, IP whitelist/blacklist)
- Custom rules and rule exclusions per vhost
- Audit logs (who changed what policy, when)

The database must support:
- Concurrent reads from the API while policies are being updated
- JSON/structured data for flexible rule configurations
- Reliable migrations as the schema evolves
- Easy local development without external dependencies

## Decision
Use **PostgreSQL 15+** for production/Docker environments and **SQLite 3** for local development and testing. Use **SQLAlchemy 2.0** as the ORM to abstract database differences.

## Rationale

1. **PostgreSQL for production** -- JSONB support for flexible policy schemas, proper concurrency (MVCC), full-text search for log filtering, and battle-tested reliability
2. **SQLite for development** -- Zero configuration, no Docker dependency for quick iteration, file-based (easy to reset/share), fast for small datasets
3. **SQLAlchemy abstraction** -- Same ORM code works with both databases. Alembic migrations generate correct SQL for each backend. Switching is a connection string change
4. **Thesis benefit** -- Demonstrating multi-database support shows architectural maturity

## Alternatives Considered

### Alternative 1: PostgreSQL Only
- **Pros**: Single database to maintain, no compatibility concerns
- **Cons**: Requires running PostgreSQL (or Docker) for any development work, slower feedback loop for quick changes
- **Rejected because**: Developer experience suffers. Running `docker-compose up` just to test an API endpoint is too heavy for fast iteration

### Alternative 2: SQLite Only
- **Pros**: Simplest possible setup, no external dependencies
- **Cons**: No JSONB (uses TEXT for JSON), limited concurrent writes, no full-text search, not suitable for production multi-user access
- **Rejected because**: Cannot handle concurrent policy updates from multiple admin sessions. Missing JSONB means losing PostgreSQL's JSON query capabilities

### Alternative 3: Redis
- **Pros**: Extremely fast, good for caching
- **Cons**: Not designed for relational data, no ACID transactions, complex queries require application-level logic, data loss risk without persistence config
- **Rejected because**: Policy data is relational (vhosts have policies, policies have rules). Redis would require reimplementing query logic that SQL handles natively

### Alternative 4: MongoDB
- **Pros**: Flexible schemas, JSON-native
- **Cons**: No ACID transactions across documents (until v4.0+, still limited), eventual consistency concerns, team more familiar with SQL, harder to express relational queries
- **Rejected because**: The data model is fundamentally relational. A vhost references a policy which contains rules -- this maps naturally to SQL tables with foreign keys

## Consequences

### Positive
- Fast local development (SQLite, no Docker needed)
- Production-grade storage (PostgreSQL, JSONB, concurrency)
- Single ORM codebase via SQLAlchemy 2.0 abstraction
- Alembic handles migrations for both backends

### Negative
- Must avoid PostgreSQL-specific SQL in application code (use SQLAlchemy abstractions)
- Some features (JSONB queries, full-text search) only work in PostgreSQL -- need graceful fallback or skip in SQLite
- Two database configurations to maintain and test

### Neutral
- Need to run integration tests against both databases in CI
- PostgreSQL adds a Docker service to the dev stack

## Implementation
- [ ] Create SQLAlchemy models with `mapped_column()` syntax (2.0 style)
- [ ] Configure Alembic for multi-database support
- [ ] Use `DATABASE_URL` env var to switch between backends
- [ ] Default to SQLite in development, PostgreSQL in Docker/production

## Validation
This decision is correct if:
- All Alembic migrations run cleanly on both PostgreSQL and SQLite
- No raw SQL queries break when switching databases
- Development workflow doesn't require Docker for basic API testing

## References
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
