---
applyTo: "**/tests/**"
---

# Test Code Instructions

Tests are a first-class part of this repo. Review them with the same rigor as production code, but with different priorities.

## What good tests look like here

- **One behavior per test.** Each test asserts a single logical outcome. Don't pile unrelated assertions into one `test_...` function.
- **Descriptive names.** `test_create_vhost_returns_409_on_duplicate_hostname` beats `test_vhost_duplicate`.
- **Arrange / Act / Assert.** Structure should be obvious from a glance. Blank lines between the three phases are fine.
- **No shared mutable state between tests.** Use fixtures; never rely on test execution order.
- **Deterministic.** No real network, no real time (`freezegun` / `vi.useFakeTimers`), no randomness without a seed.
- **Real assertions.** `assert result` on a truthy object is weak. Assert on specific fields, status codes, shapes.

## Backend tests (`src/backend/tests/`)

- **Unit** (`tests/unit/`): pure logic, no DB, no FastAPI app. Fast.
- **Integration** (`tests/integration/`):
  - Use `TestClient` against the FastAPI app.
  - Use the in-memory SQLite fixture; do not hit a real Postgres in CI tests.
  - Cover: happy path, auth required, validation failure (422), not-found (404), conflict (409), cascade behavior where relevant.
  - Do not test framework internals (FastAPI/Pydantic already tested upstream).
- **Factories / fixtures:** Prefer fixtures for common setup (user, authed client, sample vhost). Don't copy-paste setup across many tests.
- **Coverage:** aim to keep `pytest --cov=app` coverage from dropping. Flag a PR that significantly reduces coverage without justification.

## Frontend tests (`src/frontend/tests/` or co-located)

- Vitest + React Testing Library.
- Query by role / label / text (user-facing), not by `data-testid` unless no better query exists.
- Mock the network layer at the boundary (e.g. MSW or the typed API client), not deep inside components.
- No `act(...)` warnings left in test output — if one appears, the test is wrong.

## Review checklist for test diffs

1. Does the new/changed production code have a matching test? If not, request one.
2. Does the test actually exercise the new behavior (not just import the module)?
3. Is there a negative case (failure, auth rejection, validation error) alongside the happy path where relevant?
4. Are fixtures / helpers reused instead of duplicated?
5. No skipped tests (`@pytest.mark.skip`, `.skip(...)`, `xit`) sneaking in without a linked issue explaining why.
