# Project Structure - Guard Proxy

Last updated: 2026-02-22

## Current State

```
guard-proxy/
├── docs/                       # Documentation (technology stack, structure)
│   ├── stack.md                # Technology stack and rationale
│   └── structure.md            # This file
│
├── src/                        # Source code (empty - development not started)
│   ├── haproxy/                # HAProxy config files and SPOE config
│   ├── coraza/                 # Coraza WAF config, CRS rules, custom rules
│   └── panel/
│       ├── backend/            # FastAPI application (API, models, services)
│       └── frontend/           # React admin panel
│
├── configs/                    # Example configurations (empty)
├── deploy/                     # Docker Compose, systemd units (empty)
├── benchmarks/                 # Performance test scripts and payloads (empty)
│
├── README.md                   # Project overview
├── README.architecture.md      # System architecture and data flow
├── README.commands.md          # All development commands
├── README.testing.md           # Testing strategy and targets
├── progress_tracker.md         # Detailed task tracker
├── .gitignore
└── LICENSE                     # MIT
```

## Conventions

- **Directories**: `lowercase-with-hyphens/`
- **Python**: `snake_case.py`
- **TypeScript**: `PascalCase.tsx` (components), `camelCase.ts` (utilities)
- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`)
