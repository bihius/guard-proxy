---
date: 2026-02-07
tags: [decision, architecture, backend, python]
---

# ADR-001: FastAPI over Flask/Django

## Context
The Guard Proxy system requires a backend API for the policy management panel. This API will:
- Serve CRUD endpoints for virtual hosts, WAF policies, and rules
- Generate HAProxy and Coraza configuration files from stored policies
- Trigger HAProxy graceful reloads via the Runtime API
- Handle concurrent requests from the React frontend

The backend needs to be async-capable (HAProxy Runtime API calls, config file I/O), type-safe (complex policy schemas), and provide auto-generated API documentation (thesis deliverable).

## Decision
Use **FastAPI** (Python 3.11+) as the backend web framework.

## Rationale

1. **Native async/await** -- FastAPI is built on Starlette with first-class async support. This matters for non-blocking HAProxy Runtime API calls and concurrent config generation
2. **Pydantic v2 integration** -- Request/response validation is built-in. Policy schemas (paranoia levels 1-4, IP whitelists, anomaly thresholds) get validated automatically with clear error messages
3. **OpenAPI auto-generation** -- Swagger UI and ReDoc are generated automatically. This is directly useful for the thesis (API documentation chapter) and frontend development
4. **Performance** -- Comparable to Node.js/Go for I/O-bound workloads. Won't be a bottleneck given the HAProxy proxy layer handles the high-RPS traffic
5. **Type hints everywhere** -- Python type hints are enforced throughout, making the codebase more maintainable and self-documenting

## Alternatives Considered

### Alternative 1: Flask
- **Pros**: Simpler, larger ecosystem of extensions, more tutorials available
- **Cons**: Synchronous by default (async requires workarounds), no built-in validation (needs Flask-Marshmallow or similar), no auto-generated API docs without flask-restx
- **Rejected because**: Would need 3+ extensions to match what FastAPI provides out of the box. Async support is bolted on, not native

### Alternative 2: Django + Django REST Framework
- **Pros**: Batteries included (admin panel, ORM, auth), mature ecosystem
- **Cons**: Heavy for an API-only service (~30+ MB of dependencies), Django ORM is a different paradigm from SQLAlchemy, async support still evolving, opinionated structure doesn't fit our project layout
- **Rejected because**: Overkill for a purpose-built API. The built-in Django admin would conflict with our custom React panel. Django ORM lacks SQLAlchemy's flexibility for complex queries

### Alternative 3: Litestar (formerly Starlite)
- **Pros**: Similar to FastAPI, slightly faster in benchmarks, built-in dependency injection
- **Cons**: Smaller community, less documentation, fewer tutorials, less battle-tested
- **Rejected because**: For a thesis project, community support and documentation quality matter. FastAPI has more resources for troubleshooting

## Consequences

### Positive
- Clean, type-safe codebase with minimal boilerplate
- Auto-generated API docs reduce thesis documentation effort
- Async support future-proofs the architecture
- Large community means most problems are already solved on StackOverflow/GitHub

### Negative
- FastAPI's "magic" (dependency injection, auto-validation) can be confusing when debugging
- Pydantic v2 migration broke some older tutorials/examples
- Need to be careful with async -- mixing sync and async code causes subtle bugs

### Neutral
- Choosing FastAPI locks us into the ASGI ecosystem (uvicorn/hypercorn)
- SQLAlchemy 2.0 async support works well with FastAPI but requires careful session management

## Validation
This decision is correct if:
- API response times stay under 100ms for CRUD operations
- OpenAPI spec is complete enough to generate a TypeScript client
- No sync/async issues cause production bugs

## References
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [FastAPI vs Flask vs Django comparison](https://testdriven.io/blog/moving-from-flask-to-fastapi/)
