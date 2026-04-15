## Summary

- Describe the user-facing or developer-facing change.
- Link the related issue, for example: `Closes #96`.

## Testing

- [ ] `cd src/backend && uv sync --frozen --extra dev`
- [ ] `cd src/backend && uv run pytest --cov=app`
- [ ] `cd src/backend && uv run mypy app/`
- [ ] `cd src/backend && uv run ruff check app/`
- [ ] `cd src/frontend && pnpm install --frozen-lockfile`
- [ ] `cd src/frontend && pnpm run type-check`
- [ ] `cd src/frontend && pnpm run lint`

## Main Branch Protection

- [ ] In GitHub, open `Settings` -> `Branches` -> branch protection for `main`.
- [ ] Require status checks to pass before merging.
- [ ] Add `backend` and `frontend` as required checks for `main`.
