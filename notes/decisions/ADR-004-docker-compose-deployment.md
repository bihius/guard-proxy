---
date: 2026-02-07
tags: [decision, architecture, deployment, docker]
---

# ADR-004: Docker Compose for Development and Deployment

## Context
The Guard Proxy system consists of 5 services that need to work together:
1. **HAProxy** -- Reverse proxy with SPOE filter
2. **Coraza SPOA** -- WAF engine processing SPOE messages
3. **FastAPI backend** -- Policy management API
4. **React frontend** -- Admin panel (dev server or static build)
5. **PostgreSQL** -- Policy database

These services need to:
- Communicate over a shared network (HAProxy <-> Coraza via SPOE, Frontend <-> Backend via REST)
- Be reproducible across development machines and the production Proxmox server
- Start/stop together for development
- Support independent scaling and updates in production

## Decision
Use **Docker Compose** as the primary orchestration tool with three compose files:
- `docker-compose.yml` -- Base service definitions
- `docker-compose.dev.yml` -- Development overrides (hot reload, debug ports, volume mounts)
- `docker-compose.prod.yml` -- Production overrides (optimized builds, restart policies, resource limits)

For production, deploy on **Proxmox VE** using LXC containers running Docker.

## Rationale

1. **Single command startup** -- `docker-compose up` starts all 5 services with correct networking, volumes, and environment. Critical for reproducibility in a thesis project
2. **Network isolation** -- Docker networks handle service discovery (HAProxy reaches Coraza at `coraza:9000`). No port conflicts with host services
3. **Multi-file composition** -- Base + override pattern keeps configs DRY. Development gets hot-reload and debug ports; production gets resource limits and restart policies
4. **Proxmox compatibility** -- Docker Compose runs inside LXC containers on Proxmox. This matches the planned production deployment (3 LXC containers: proxy, panel, monitoring)
5. **Thesis reproducibility** -- Anyone reviewing the thesis can clone the repo and run `docker-compose up` to see the system working. This is a strong demonstration for the defense

## Alternatives Considered

### Alternative 1: Kubernetes (k8s)
- **Pros**: Industry standard for production, auto-scaling, self-healing, service mesh
- **Cons**: Massive operational complexity for 5 services, requires a cluster (minikube/kind for dev), YAML verbosity, steep learning curve
- **Rejected because**: Wildly over-engineered for a thesis project with a single user. The operational overhead of running k8s would consume weeks better spent on WAF implementation

### Alternative 2: Manual Docker Commands + Scripts
- **Pros**: No Compose dependency, full control over each container
- **Cons**: Networking setup becomes manual (`docker network create`, `--network` flags), starting order must be scripted, environment variables need a custom solution
- **Rejected because**: Compose solves all of these problems declaratively. Shell scripts would just be a worse version of docker-compose.yml

### Alternative 3: Bare Metal (No Containers)
- **Pros**: No Docker overhead, simpler debugging, direct access to processes
- **Cons**: Environment differences between machines (macOS vs Linux), dependency conflicts (Python versions, Go versions), no isolation between services, hard to reproduce
- **Rejected because**: "It works on my machine" is unacceptable for a thesis. Docker guarantees the reviewer sees the same environment

### Alternative 4: Podman Compose
- **Pros**: Daemonless, rootless by default, Docker CLI compatible
- **Cons**: Podman Compose is less mature than Docker Compose, some Docker Compose features missing, smaller community
- **Rejected because**: Docker Compose is better documented and more widely supported. Podman compatibility can be added later if needed

## Consequences

### Positive
- One-command development environment setup
- Reproducible across machines (macOS, Linux)
- Clear service isolation and networking
- Production deployment mirrors development closely
- Thesis reviewers can run the system themselves

### Negative
- Docker adds resource overhead (RAM, CPU) compared to bare metal
- Build times for custom images (Coraza, backend) add to feedback loop
- macOS Docker Desktop performance is slower than native Linux Docker
- Need to maintain Dockerfiles for custom services (Coraza, backend)

### Neutral
- HAProxy official Docker image is well-maintained
- PostgreSQL official Docker image handles initialization scripts
- Volume mounts for development enable hot-reload but can have file-watching issues on macOS

## Implementation
- [ ] Create `deploy/docker/docker-compose.yml` with all 5 services
- [ ] Create `deploy/docker/docker-compose.dev.yml` with dev overrides
- [ ] Create `deploy/docker/docker-compose.prod.yml` with production settings
- [ ] Create `src/coraza/Dockerfile` for custom Coraza SPOA image
- [ ] Create `.env.example` with all required environment variables
- [ ] Add `Makefile` targets: `make dev`, `make prod`, `make down`

## Planned Service Configuration

| Service | Image | Ports | Notes |
|---------|-------|-------|-------|
| haproxy | haproxy:2.8 | 80, 443 | SPOE filter, custom config mount |
| coraza | custom build | 9000 (SPOE) | Go binary with CRS rules |
| backend | custom build | 8000 | FastAPI + uvicorn |
| frontend | node:20 (dev) / nginx (prod) | 3000 (dev) | Vite dev server or static build |
| postgres | postgres:15 | 5432 | Init script for schema |

## Validation
This decision is correct if:
- `docker-compose up` brings all services to healthy state in <60 seconds
- HAProxy successfully communicates with Coraza over SPOE within Docker network
- Development workflow (edit code -> see changes) takes <5 seconds with hot-reload
- The system can be demonstrated on a fresh machine with only Docker installed

## References
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [HAProxy Docker Image](https://hub.docker.com/_/haproxy)
- [PostgreSQL Docker Image](https://hub.docker.com/_/postgres)
