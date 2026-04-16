---
applyTo: "src/backend/**"
---

# Backend (FastAPI + SQLAlchemy) Instructions

The backend lives in `src/backend/`. It uses Python 3.13, FastAPI, SQLAlchemy, Alembic, Pydantic v2, and `pydantic-settings`. Dependencies are managed with `uv`; the lockfile is `uv.lock`.

## Quality gates for any backend change

Run from `src/backend/`:

1. `uv sync --frozen --extra dev`
2. `uv run pytest --cov=app`
3. `uv run mypy app/`
4. `uv run ruff check app/`

If a PR changes code under `src/backend/app/` without addressing any of these, flag it.

## Conventions to enforce in reviews

- **Type hints everywhere.** Public functions, route handlers, service methods, and repository methods must be fully typed. `Any` is a smell — ask for a concrete type unless there's a justified reason.
- **Pydantic v2 syntax.** Use `model_config = ConfigDict(...)`, `Field(...)`, `model_validate`, `model_dump`. Reject v1 patterns like `class Config:` or `.dict()` in new code.
- **Settings.** All configuration goes through the `pydantic-settings` `Settings` object. Never read `os.environ` directly in route/service code.
- **Database access.**
  - Use the injected `AsyncSession` / `Session` dependency; do not create ad-hoc sessions inside handlers.
  - Queries should use SQLAlchemy 2.x style (`select(...)`, `session.execute(...)`, `.scalars()`), not the legacy `Query` API.
  - Any model change must ship with an Alembic revision. Check `src/backend/alembic/versions/` for a new file in the PR.
  - Destructive migrations (drop column/table, non-null without default, type change) need an explicit note in the PR description.
- **Route handlers.**
  - Thin handlers: validate input (Pydantic schema), delegate to a service/repository, return a response schema.
  - Always declare `response_model=` for non-trivial endpoints.
  - Raise `HTTPException` with proper status codes (`400`, `401`, `403`, `404`, `409`, `422`, `500`). Do not return plain dicts with `{"error": ...}` and a 200.
- **Auth.**
  - JWT secrets come from settings. No hardcoded keys, no committed `.env`.
  - Protected routes must declare an auth dependency; spot-check that new protected routes actually require a valid user.
  - Password hashing: use the existing hashing utility (bcrypt/argon2 via `passlib`/`argon2-cffi`); never store plaintext.
- **Error handling.** No bare `except:`. Catch specific exceptions. If you catch and log, include context but never include secrets or full auth headers.
- **Logging.** Use the configured logger, not `print`. Structure messages so they are useful in production (`logger.info("vhost created", extra={"vhost_id": v.id})`).
- **Async vs sync.** Do not mix blocking I/O inside `async def` handlers (no blocking `requests`, blocking file I/O, or sync DB calls). Use the async client / async session.

## Tests

- **Unit tests** (`src/backend/tests/unit/`): isolated, no DB, no network. Cover schemas, config generation, pure helpers.
- **Integration tests** (`src/backend/tests/integration/`): FastAPI `TestClient` + in-memory SQLite fixture. Cover happy path, auth failure, validation failure, and key relational behavior (e.g. cascade deletes, unique constraints).
- New endpoint → at least one happy-path and one failure-case test.
- New model → at least one test exercising key constraints and relationships.

## HAProxy / Coraza config generation

If the PR touches code that emits HAProxy config, SPOE config, or Coraza rules:

- There must be a unit test asserting the rendered output for a representative input.
- The generated config must be validated with `haproxy -c -f configs/haproxy/haproxy.cfg` (once `configs/haproxy/` is present in the repo). If it isn't yet, note that this gate is deferred.
- Never interpolate user-provided values into config without escaping / validation — this is a direct injection risk.
