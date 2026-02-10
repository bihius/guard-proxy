---
date: 2026-02-07
tags: [decision, architecture, frontend]
---

# ADR-003: React + TypeScript for Frontend Panel

## Context
The Guard Proxy system needs an admin panel for managing WAF policies. The panel will include:
- Dashboard with traffic metrics and recent activity
- Virtual host management (CRUD with forms)
- Policy editor (paranoia levels, anomaly thresholds, IP lists, rule exclusions)
- Log viewer with filtering and pagination

The frontend is an internal admin tool, not a public-facing website. It needs to be functional, maintainable, and reasonably polished -- but not a design showcase.

## Decision
Use **React 18** with **TypeScript 5** (strict mode), **Vite 5** as build tool, **TanStack Query** for server state, **React Hook Form** for forms, and **shadcn/ui** (Radix UI + Tailwind CSS 3) for components.

## Rationale

1. **React** -- Largest ecosystem, most libraries, best TypeScript support among UI frameworks. Finding solutions to problems is easier due to community size
2. **TypeScript strict mode** -- The API returns complex nested objects (policies with rules, vhosts with configs). Type safety prevents runtime errors when the API schema changes
3. **Vite** -- Instant HMR, fast builds. Development experience is significantly better than webpack-based setups
4. **TanStack Query** -- Eliminates manual loading/error/cache state management for API calls. Built-in refetching, optimistic updates, and pagination support match our use cases exactly
5. **shadcn/ui** -- Copy-paste components (not an npm dependency), so we own the code. Built on Radix UI (accessible) + Tailwind (utility-first). Good-looking defaults with zero design effort
6. **React Hook Form** -- The policy editor has complex forms (dynamic IP lists, rule selection, nested config). RHF handles this with minimal re-renders

## Alternatives Considered

### Alternative 1: Vue 3 + Vuetify
- **Pros**: Simpler learning curve, Vuetify provides complete component library, good documentation
- **Cons**: Smaller TypeScript ecosystem, fewer third-party libraries, Vuetify can be rigid for custom layouts
- **Rejected because**: TypeScript support in Vue is good but React's is more mature. Fewer community resources for solving edge cases

### Alternative 2: Svelte + SvelteKit
- **Pros**: Smallest bundle size, simplest reactivity model, no virtual DOM overhead
- **Cons**: Smallest ecosystem of the three, fewer UI component libraries, TypeScript support is newer and less mature
- **Rejected because**: For an admin panel, bundle size doesn't matter much. The ecosystem gap means more code written from scratch (tables, dialogs, forms). Risk for a thesis project where time is limited

### Alternative 3: Plain HTML/CSS + htmx
- **Pros**: Simplest possible stack, server-rendered, no build step, minimal JavaScript
- **Cons**: Limited interactivity for complex forms (policy editor), no component reuse, harder to implement real-time updates
- **Rejected because**: The policy editor requires dynamic form behavior (add/remove IP entries, toggle rule sets, preview config). This would be painful with htmx alone

### Alternative 4: Next.js (React framework)
- **Pros**: SSR, file-based routing, API routes built-in
- **Cons**: Overkill for an SPA admin panel, adds complexity (server components, hydration), heavier deployment
- **Rejected because**: We don't need SSR or SEO. The panel is a client-side SPA behind authentication. Vite is simpler and faster for this use case

## Consequences

### Positive
- Type-safe frontend that catches errors at compile time
- Rich ecosystem of React libraries for any need
- shadcn/ui provides professional-looking UI with minimal effort
- TanStack Query eliminates most hand-written data fetching logic
- Fast development with Vite HMR

### Negative
- React's mental model (hooks, effects, closures) has a learning curve
- shadcn/ui components need manual installation (copy-paste per component)
- Tailwind's utility classes make HTML verbose

### Neutral
- Need to maintain TypeScript types that mirror the FastAPI Pydantic schemas (could auto-generate from OpenAPI spec)
- pnpm as package manager (faster than npm, disk-efficient)

## Validation
This decision is correct if:
- Policy editor handles complex forms without UX issues
- TypeScript catches API contract mismatches at compile time
- Development velocity stays high (features in hours, not days)

## References
- [React Documentation](https://react.dev/)
- [shadcn/ui](https://ui.shadcn.com/)
- [TanStack Query](https://tanstack.com/query/)
