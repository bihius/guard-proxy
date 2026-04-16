---
date: 2026-04-16
tags: [decision, architecture, backend, database]
---

# ADR-006: Synchronous SQLAlchemy for MVP

## Context
ADR-001 selected FastAPI partly for native async support, but the current backend implementation is fully synchronous.

Current backend database shape:
- `src/backend/app/database.py` uses `create_engine(...)` and `sessionmaker(class_=Session)`
- `get_db()` yields a synchronous `Session`
- Routers in `src/backend/app/routers/` use `def` endpoints with `db: Session = Depends(get_db)`

The contract between ADR-001 and the codebase is therefore inconsistent. We must decide whether to align code with async SQLAlchemy now, or align ADRs with synchronous SQLAlchemy for the MVP.

## Decision
Use **synchronous SQLAlchemy 2.0** (`Session` + `create_engine`) for the MVP.

FastAPI supports this model by running synchronous path operations in a threadpool, so blocking database calls do not block the event loop directly. We keep async SQLAlchemy as a possible future migration when a concrete workload requires it.

## Rationale

1. **Code reality and low-risk alignment** -- The current backend is already built around synchronous session usage. Choosing sync for MVP aligns decisions with implementation without broad refactors.
2. **MVP-first scope control** -- Migrating to async SQLAlchemy now would touch every router, service, dependency, and many tests. That cost does not unlock critical MVP functionality today.
3. **Team familiarity and test simplicity** -- Current patterns, fixtures, and endpoint structure are built around synchronous SQLAlchemy. Keeping this model reduces immediate complexity.
4. **Future path remains open** -- FastAPI and SQLAlchemy support async migration later. Deferring now does not block a focused migration if runtime characteristics demand it.

## Alternatives Considered

### Alternative 1: Migrate now to async SQLAlchemy
- **Pros**: Matches the original async framing in ADR-001; better fit for high-concurrency and I/O-heavy request paths
- **Cons**: Requires large, cross-cutting changes to routers, services, dependency wiring, and tests during MVP build-out
- **Rejected because**: The migration effort is high relative to current MVP needs, and there is no measured bottleneck requiring it yet

## Consequences

### Positive
- ADRs align with actual backend implementation
- No broad backend refactor is required in M0
- Tests and developer workflows stay straightforward
- Team can continue with known SQLAlchemy patterns

### Negative
- Sync DB operations still consume threadpool workers under heavy concurrency
- If runtime/API interactions become highly concurrent, async migration pressure increases
- Future migration will still require coordinated refactoring work

### Neutral
- SQLAlchemy 2.0 supports both sync and async session models
- The project can reevaluate this decision later based on profiling and production-like load tests

## When To Revisit
Reopen this decision when one or more of the following conditions appear:
- Request concurrency increases enough to show threadpool saturation
- HAProxy runtime/control-plane interactions become a hot-path I/O workload
- Load tests show database access as a measurable throughput bottleneck

## Validation
This decision is correct if:
- ADR-001 no longer claims that async SQLAlchemy is already adopted
- Backend documentation and code remain consistent on sync session usage
- MVP work proceeds without async migration blocking product milestones

## References
- [ADR-001: FastAPI over Flask/Django](ADR-001-fastapi-over-flask-django.md)
- [ADR-002: PostgreSQL for Production, SQLite for Development](ADR-002-postgresql-with-sqlite-dev.md)
- [Issue #98: ADR-006 sync vs async SQLAlchemy decision](https://github.com/bihius/guard-proxy/issues/98)
- [FastAPI: Concurrency and async / await](https://fastapi.tiangolo.com/async/)
