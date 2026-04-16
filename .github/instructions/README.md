# GitHub Copilot Instructions

This folder holds path-scoped instructions for GitHub Copilot code review and Copilot Chat.

Each `*.instructions.md` file starts with a frontmatter `applyTo` glob. Copilot automatically applies the instructions whose `applyTo` matches the files being reviewed or edited.

| File | Scope | Purpose |
|------|-------|---------|
| `general.instructions.md` | `**` | How Copilot should review PRs and propose small changes in this repo. |
| `backend.instructions.md` | `src/backend/**` | Python / FastAPI / SQLAlchemy conventions and quality gates. |
| `frontend.instructions.md` | `src/frontend/**` | React / TypeScript / Tailwind conventions and quality gates. |
| `tests.instructions.md` | `**/tests/**` | What good tests look like; how to review test diffs. |
| `security.instructions.md` | `**` | Security-focused review checklist (this repo is a WAF). |

## How to update

1. Keep instructions short, concrete, and actionable — Copilot has a limited context budget.
2. Do not duplicate what lives in `CLAUDE.md` / `AGENTS.md`; point to them instead when appropriate.
3. When the project conventions change (e.g. we adopt a new linter, migration tool, or framework version), update the matching file here in the same PR.
4. Prefer adding a new narrowly-scoped file over bloating `general.instructions.md`.

## Related

- `CLAUDE.md` / `AGENTS.md` — canonical AI-agent policy for human-triggered agents (Claude Code, Codex, Cursor).
- `.github/pull_request_template.md` — PR checklist aligned with the quality gates above.
