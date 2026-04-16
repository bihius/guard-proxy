---
applyTo: "src/frontend/**"
---

# Frontend (React + TypeScript + Vite) Instructions

The frontend lives in `src/frontend/`. Stack: React, TypeScript (strict), Vite, Tailwind CSS, Vitest. Package manager is **pnpm only** — do not suggest `npm` or `yarn` commands.

## Quality gates for any frontend change

Run from `src/frontend/`:

1. `pnpm install --frozen-lockfile`
2. `pnpm run type-check`
3. `pnpm run lint`
4. `pnpm test` (when tests are present / touched)

If a PR changes code under `src/frontend/src/` without addressing these, flag it.

## Conventions to enforce in reviews

- **TypeScript strictness.**
  - No `any`. Use `unknown` and narrow, or define a proper type. If `any` is unavoidable, it must have a short comment explaining why.
  - No `// @ts-ignore` / `// @ts-expect-error` without a justification comment and, ideally, a linked issue.
  - Prefer `type` for unions/aliases and `interface` for object contracts that may be extended.
- **React patterns.**
  - Function components only, with hooks. No class components.
  - Keep components focused; extract hooks (`useSomething`) for non-trivial logic.
  - Stable keys for lists — never use array index as a key when the list can reorder.
  - Hooks must obey the rules of hooks (top-level, not conditional). Dependencies arrays for `useEffect` / `useMemo` / `useCallback` must be complete; do not silence the exhaustive-deps lint without justification.
- **State & data fetching.**
  - Use the project's existing data-fetching layer (e.g. a typed API client / React Query hook) rather than raw `fetch` scattered in components.
  - Do not put secrets, tokens, or internal URLs into client-side code; backend origin is configured via env at build time.
- **Forms & validation.** Validate on the client for UX, but always rely on the backend for authoritative validation. Surface backend 4xx errors to the user clearly.
- **Styling.** Tailwind utility classes over ad-hoc CSS. Reuse existing design tokens/classes; do not introduce a parallel styling approach (styled-components, CSS modules) without discussion.
- **Accessibility.**
  - Interactive elements must be real buttons/links, not clickable `<div>`s.
  - Form inputs need associated `<label>`s.
  - Images need `alt` text (empty `alt=""` only for decorative images).
- **Imports.** No deep imports into third-party packages' internals. Use the package's public API.

## API contract

- Types for API requests/responses should match the backend Pydantic schemas. If a backend schema changed in the same PR (or a related one), the frontend types must be updated together.
- Do not hand-roll parallel type definitions if a generator or shared schema source is in use.

## Tests

- Frontend tests live under `src/frontend/tests/` (or co-located `*.test.ts(x)`), using Vitest and React Testing Library.
- New non-trivial components or hooks should have at least a basic render / behavior test.
- Test user-visible behavior, not implementation details (avoid asserting on internal state).
