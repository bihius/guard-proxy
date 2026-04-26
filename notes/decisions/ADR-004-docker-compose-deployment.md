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
Use **Docker Compose** as the primary orchestration tool for the local and
MVP deployment stack.

For production, deploy on **Proxmox VE** using LXC containers running Docker.

## Current M1 Implementation

M1 implements the full local stack with:
- `deploy/docker/docker-compose.yml` as the base five-service stack.
- `deploy/docker/docker-compose.debug.yml` as the debug overlay used by `make dev`.
- `deploy/docker/coraza.Dockerfile` building from `ghcr.io/corazawaf/coraza-spoa:0.6.1`.
- `haproxy:3.0-alpine` exposed as host port `8080` and configured from `configs/haproxy/`.
- `postgres:16-alpine`, backend, frontend, Coraza, and HAProxy health checks.
- Named volumes for PostgreSQL data, HAProxy logs, Coraza logs, backend logs, and generated config.
- Make targets for `run`, `dev`, `down`, `clean`, `logs`, `ps`, `seed`, and `coraza-build`.

Production-specific compose overlays remain future work; the implemented M1
deployment target is reproducible local Docker Compose.

## Rationale

1. **Single command startup** -- `docker-compose up` starts all 5 services with correct networking, volumes, and environment. Critical for reproducibility in a thesis project
2. **Network isolation** -- Docker networks handle service discovery (HAProxy reaches Coraza at `coraza:9000`). No port conflicts with host services
3. **Multi-file composition** -- Base + override patterns can keep configs DRY. The current M1 stack uses a base file plus a debug overlay; production overlays remain future work.
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

## Implementation Status

- [x] Create `deploy/docker/docker-compose.yml` with all 5 services
- [x] Create `deploy/docker/docker-compose.debug.yml` with debug overrides
- [x] Create `deploy/docker/coraza.Dockerfile` for the pinned Coraza SPOA image
- [x] Create `deploy/docker/.env.example` with required environment variables
- [x] Add Makefile targets for local stack operation and troubleshooting
- [ ] Add production-specific compose overlays when production deployment is in scope

## M1 Service Configuration

| Service | Image | Ports | Notes |
|---------|-------|-------|-------|
| haproxy | `haproxy:3.0-alpine` | `8080:80` | SPOE filter, WAF enforcement, config mounts |
| coraza | `ghcr.io/corazawaf/coraza-spoa:0.6.1` via `deploy/docker/coraza.Dockerfile` | `9000` internal | Coraza SPOA with mounted CRS rules |
| backend | custom build from `src/backend/Dockerfile` | `8000` internal | FastAPI + uvicorn |
| frontend | custom build from `src/frontend/Dockerfile` | `3000:5173` | Vite dev server |
| postgres | `postgres:16-alpine` | `5432` internal | Policy and log storage |

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
