# Base images are pinned by digest; see "Pinned component versions" in
# docs/architecture.md before bumping.
FROM python:3.13.16-slim-trixie@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.6

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13.16-slim-trixie@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
# The shared `generated_config` volume is mounted here in the backend but at
# /etc/haproxy/generated in the HAProxy container. haproxy.cfg bakes in the
# absolute cert path /etc/haproxy/generated/certs, so alias it to the backend's
# mount point; this lets `haproxy -c` validation resolve the same shared certs
# directory HAProxy uses at runtime, without duplicating the volume mount.
RUN mkdir -p /var/lib/guard-proxy/generated/crs \
    && chown app:app /app /var/lib/guard-proxy/generated /var/lib/guard-proxy/generated/crs \
    && mkdir -p /etc/haproxy \
    && ln -s /var/lib/guard-proxy/generated /etc/haproxy/generated

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 755 /usr/local/bin/docker-entrypoint.sh

# `haproxy -c` here validates every generated haproxy.cfg before the haproxy
# container loads it, so this must be the same HAProxy release as the haproxy
# image in docker/docker-compose.yml and release/docker-compose.yml
# (.github/scripts/check_version_pins.py enforces it). The backports suite is
# derived from the version, e.g. 3.0.29-1~bpo12+1 -> bookworm-backports-3.0.
ARG HAPROXY_DEB_VERSION=3.0.29-1~bpo12+1
RUN haproxy_branch="${HAPROXY_DEB_VERSION%%-*}" \
    && haproxy_branch="${haproxy_branch%.*}" \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg certbot \
    && curl -fsSL https://haproxy.debian.net/bernat.debian.org.gpg \
       | gpg --dearmor > /etc/apt/trusted.gpg.d/haproxy.gpg \
    && printf "deb [signed-by=/etc/apt/trusted.gpg.d/haproxy.gpg] http://haproxy.debian.net bookworm-backports-%s main\n" "${haproxy_branch}" \
       > /etc/apt/sources.list.d/haproxy.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends "haproxy=${HAPROXY_DEB_VERSION}" \
    && apt-get purge -y curl gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app alembic alembic
COPY --chown=app:app app app
COPY --chown=app:app scripts scripts
COPY --chown=app:app alembic.ini alembic.ini
# The project itself isn't installed as a distribution above (--no-install-project),
# so no dist-info exists for importlib.metadata to read. Ship pyproject.toml so
# app.main can fall back to parsing the version straight from it.
COPY --chown=app:app pyproject.toml pyproject.toml

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
