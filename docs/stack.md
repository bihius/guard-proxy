# Technology Stack - Guard Proxy

> Self-hosted Reverse Proxy WAF with HAProxy and OWASP Coraza

Last updated: 2026-02-15

---

### TL;DR

| Category | Technologies |
|----------|-------------|
| **Proxy & WAF** | HAProxy, Coraza, OWASP CRS |
| **Backend** | FastAPI, SQLAlchemy, PostgreSQL |
| **Frontend** | React, TypeScript, Vite, TanStack Query, Tailwind |
| **Infrastructure** | Docker Compose, Prometheus, Grafana |
| **Testing** | pytest, Vitest, wrk, OWASP ZAP |

---

## Core Technologies

### HAProxy 2.8+
**Role**: Reverse Proxy with SPOE
**Why**: Industry-standard, battle-tested, SPOE support for external processing

Key features:
- SPOE (Stream Processing Offload Engine) for async WAF processing
- SSL/TLS termination
- Load balancing and virtual host routing
- High performance under load

Alternatives considered:
- Nginx: No native SPOE support, would require custom modules
- Traefik: Limited WAF integration options

---

### Coraza WAF 3.x
**Role**: Web Application Firewall (SPOA)
**Why**: Modern Go-based WAF engine, fully OWASP CRS compatible, actively maintained

Key features:
- Written in Go (fast, memory-safe)
- 100% OWASP CRS 4.x compatible
- Native SPOA implementation
- Active development community

Alternatives considered:
- ModSecurity 2.x: In maintenance mode, C codebase
- ModSecurity 3.x: Less mature libmodsecurity, harder to deploy standalone

---

### OWASP ModSecurity CRS 4.x
**Role**: WAF Rule Set
**Why**: Industry-standard rule set with comprehensive coverage

Key features:
- Protection against OWASP Top 10
- Paranoia Levels (PL1-PL4) for tunable strictness
- Anomaly scoring system
- Regular updates and extensive documentation

---

## Backend

### FastAPI (Python 3.12)
**Role**: Policy Management API
**Why**: Modern async framework with built-in validation and auto-generated API docs

Key features:
- Async/await native
- Pydantic v2 validation
- OpenAPI/Swagger auto-generation

Alternatives considered:
- Flask: Synchronous, no built-in validation
- Django: Too heavy for API-only use case


---

### SQLAlchemy 2.0 + Alembic
**Role**: ORM and database migrations
**Why**: Mature, async support, works with multiple backends

---

### PostgreSQL 15+
**Role**: Production database
**Why**: Robust, JSONB support for flexible schemas, ACID compliant

Development alternative: SQLite 3 (zero-config, file-based)


---

## Frontend

### React 18 + TypeScript
**Role**: Admin panel UI
**Why**: Mature ecosystem, strong TypeScript support

Alternatives considered:
- Vue: Smaller ecosystem for enterprise patterns
- Svelte: Less mature, smaller community

See: ADR-003 (React + TypeScript)

---

### Vite + Tailwind CSS + shadcn/ui
**Role**: Build tooling and styling
**Why**: Fast build times, utility-first CSS, copy-paste component library (no dependency lock-in)

---

### TanStack Query
**Role**: Server state management
**Why**: Simplifies API data fetching with caching, background refetching, and pagination

---

## Infrastructure

### Docker Compose
**Role**: Containerization and deployment
**Why**: Consistent environments, easy multi-service orchestration


---

### Prometheus + Grafana + Loki
**Role**: Monitoring and observability
**Why**: Industry standard for metrics, dashboards, and log aggregation

---

## Testing & Security Tools

- **pytest** - Python unit/integration testing
- **Vitest** - Frontend testing (Vite-native)
- **k6** - Load testing and benchmarking
- **OWASP ZAP** - Automated security scanning

---

## Development Tools

- **uv** - Python package manager (faster than pip)
- **pnpm** - Node package manager (disk-efficient)
- **Ruff** - Python linter/formatter (Rust-based, fast)
- **ESLint + Prettier** - TypeScript linting/formatting



