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
RUN mkdir -p /var/lib/guard-proxy/generated/crs && chown app:app /app /var/lib/guard-proxy/generated /var/lib/guard-proxy/generated/crs

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

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
