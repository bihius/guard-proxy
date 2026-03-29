# Guard Proxy — Frontend

Admin panel for Guard Proxy WAF. React 18 + TypeScript + Vite + Tailwind CSS v4.

## Quick Start

```bash
pnpm install
pnpm run dev        # dev server on http://localhost:5173
pnpm run build      # production build
pnpm run type-check # TypeScript compiler check
pnpm run lint       # ESLint
```

Backend must be running at `http://127.0.0.1:8000` (or set `VITE_API_BASE_URL` in `.env`).
Copy `.env.example` to `.env` if you need to change the backend URL.

## Stack

- **pnpm** — package manager (no npm/yarn)
- **React 18** + **TypeScript** (strict)
- **Vite 6** — bundler
- **Tailwind CSS v4** — styling (via `@tailwindcss/vite`)
- **React Router v6** — client-side routing
- Custom design system with CSS custom properties and oklch color tokens

## Project Structure

```
src/
  main.tsx                      # entry point
  app/
    App.tsx                     # root component
    router.tsx                  # all routes
    providers.tsx               # context providers
  pages/                        # one folder per route
    login/LoginPage.tsx
    dashboard/DashboardPage.tsx
    vhosts/VHostsPage.tsx
    vhosts/VHostDetailPage.tsx
    policies/PoliciesPage.tsx
    forbidden/ForbiddenPage.tsx
  layouts/
    AppLayout.tsx               # topbar + content area
  components/
    layout/NavBar.tsx           # top navigation bar
    shared/                     # reusable UI components
      PageHeader.tsx
      SectionCard.tsx
      StatCard.tsx
      StatusBadge.tsx
      RoleBadge.tsx
      EmptyState.tsx
      LoadingState.tsx
      ErrorState.tsx
      PagePlaceholder.tsx
  features/
    auth/                       # auth context, login API, token storage
  hooks/
    use-auth.ts                 # hook for auth context
  lib/
    api-client.ts               # shared API client (apiRequest + ApiError)
  types/
    api.ts                      # shared API types (CurrentUser, TokenResponse, etc.)
  styles/
    globals.css                 # design tokens, themes, base styles
```

## Key Patterns

### API Requests

All requests go through `apiRequest()` in `lib/api-client.ts`:

```typescript
import { apiRequest } from "@/lib/api-client";
const data = await apiRequest<MyType>("/endpoint", { method: "GET", token });
```

Errors throw `ApiError` with `.status` and `.detail`.

### Auth

Auth state lives in `features/auth/auth-context.tsx`. Access via the `useAuth()` hook:

```typescript
import { useAuth } from "@/hooks/use-auth";
const { user, isAuthenticated, signIn, signOut, hasRole } = useAuth();
```

### Route Protection

- `ProtectedRoute` — redirects unauthenticated users to `/login`
- `PublicOnlyRoute` — redirects authenticated users to `/dashboard`
- `RoleRoute` — restricts by role (exported but not yet wired)

### Shared Components

Build new screens using existing shared components in `components/shared/`:

- `PageHeader` — page title with eyebrow label and action buttons
- `SectionCard` — card with title, description, icon, and children
- `StatCard` — metric card with label, value, tone, and icon
- `StatusBadge` — colored pill badge (success/warning/error/info/neutral)
- `RoleBadge` — badge showing user role
- `EmptyState`, `LoadingState`, `ErrorState` — standard state placeholders
- `PagePlaceholder` — full placeholder page for routes not yet built

### Design Tokens

Colors and radii are CSS custom properties defined in `styles/globals.css`.
Two themes: **emerald** (default, green) and **frost** (blue). Use the token names
in Tailwind classes (e.g. `text-fg`, `bg-surface`, `text-accent`, `border-border`).

### Icons

Inline SVG components defined alongside the components that use them.
No external icon library.

## Backend API Endpoints (available now)

| Method | Endpoint | Auth |
|--------|----------|------|
| `POST` | `/auth/login` | public |
| `POST` | `/auth/refresh` | token |
| `GET` | `/auth/me` | token |
| `GET/POST` | `/vhosts` | token (write = admin) |
| `GET/PATCH/DELETE` | `/vhosts/{id}` | token (write = admin) |
| `GET/POST` | `/policies` | token (write = admin) |
| `GET/PATCH/DELETE` | `/policies/{id}` | token (write = admin) |
| `GET` | `/health` | public |

Swagger docs: `http://127.0.0.1:8000/docs`

## What Not to Change Without Asking

- `styles/globals.css` design tokens and theme system
- `features/auth/` auth context architecture
- `lib/api-client.ts` shared API client
- `app/router.tsx` route structure
- `components/layout/NavBar.tsx` navigation

## Mocks

Dashboard currently shows hardcoded placeholder data. Replace with real API
calls when the corresponding endpoints are ready.
