# Guard Proxy

> Self-hosted Reverse Proxy WAF with HAProxy and OWASP Coraza

## About

Guard Proxy is a Web Application Firewall (WAF) solution designed for self-hosted environments. It combines HAProxy as a reverse proxy with Coraza WAF engine and OWASP Core Rule Set for threat detection, managed through a web-based admin panel.

This project is being developed as a master's thesis (praca inzynierska) at Wroclaw University of Science and Technology.

## Planned Features

- **HAProxy 2.8+** as reverse proxy with SPOE integration
- **Coraza WAF 3.x** with OWASP CRS for threat detection
- **Per-vhost policies** with configurable paranoia levels (PL1-PL4)
- **Anomaly scoring** for intelligent threat detection
- **Admin panel** (FastAPI + React) for managing policies and monitoring
- **Docker-based deployment** for easy setup

## Architecture (Planned)

```
Client -> HAProxy (reverse proxy + SPOE) -> Coraza SPOA (WAF engine)
                                                |
                                           Allow / Deny
                                                |
                                          Backend Apps

Management: React UI -> FastAPI -> PostgreSQL
```

## Tech Stack

- **Proxy**: HAProxy 2.8+ with SPOE
- **WAF**: Coraza 3.x + OWASP CRS 4.x
- **Backend**: Python 3.12, FastAPI, SQLAlchemy, PostgreSQL
- **Frontend**: React, TypeScript, Tailwind CSS
- **Infrastructure**: Docker Compose, Prometheus, Grafana

Full details: [Technology Stack](docs/stack.md)

## Project Status

**Status**: Early development (Phase 1: Research & Foundation)

See [progress.md](progress.md) for detailed task breakdown.

## Documentation

- [Technology Stack](docs/stack.md) - Technologies and rationale
- [Project Structure](docs/structure.md) - Directory organization

## License

MIT License - see [LICENSE](LICENSE)
