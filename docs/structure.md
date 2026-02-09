# Project Structure - Guard Proxy

Last updated: 2026-02-09

## Current State

```
guard-proxy/
├── docs/                       # Documentation
│   ├── stack.md                # Technology stack and rationale
│   ├── structure.md            # This file
│   └── thesis/                 # Thesis document
│       └── praca_inz_52703.docx
│
├── src/                        # Source code (empty - development not started)
├── deploy/                     # Deployment configs (empty)
├── configs/                    # Example configurations (empty)
├── benchmarks/                 # Performance testing (empty)
│
├── .gitignore
├── README.md
├── progress.md                 # Detailed task tracker
└── LICENSE                     # MIT
```

## Planned Structure

As development progresses, `src/` will contain:

- `src/haproxy/` - HAProxy configuration files and SPOE config
- `src/coraza/` - Coraza WAF config, CRS rules, custom rules
- `src/panel/backend/` - FastAPI application (API, models, services)
- `src/panel/frontend/` - React admin panel

`deploy/` will contain Docker Compose files and monitoring configs (Prometheus, Grafana).

`benchmarks/` will hold performance test scripts and security scan payloads.

## Conventions

- **Directories**: `lowercase-with-hyphens/`
- **Python**: `snake_case.py`
- **TypeScript**: `PascalCase.tsx` (components), `camelCase.ts` (utilities)
- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`)
