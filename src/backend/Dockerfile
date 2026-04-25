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

RUN groupadd --system app && useradd --system --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
RUN chown app:app /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app alembic alembic
COPY --chown=app:app app app
COPY --chown=app:app scripts scripts
COPY --chown=app:app alembic.ini alembic.ini

EXPOSE 8000

USER app
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
