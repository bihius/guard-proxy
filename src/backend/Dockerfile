FROM python:3.13-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.6

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim

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

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg certbot \
    && curl -fsSL https://haproxy.debian.net/bernat.debian.org.gpg \
       | gpg --dearmor > /etc/apt/trusted.gpg.d/haproxy.gpg \
    && printf "deb [signed-by=/etc/apt/trusted.gpg.d/haproxy.gpg] http://haproxy.debian.net bookworm-backports-3.0 main\n" \
       > /etc/apt/sources.list.d/haproxy.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends haproxy \
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
