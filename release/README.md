# Guard Proxy — beta install guide

This release kit runs Guard Proxy from prebuilt images published to GHCR.
It does not require cloning the source repository or building anything
locally.

**Beta status.** This is a pre-release build for early testers. Expect
rough edges. Ban/rate-limit state, generated configs, and the database are
all persisted in Docker volumes, but no upgrade-path guarantees are made
between beta releases yet — back up `pgdata` before upgrading. See
[Known limitations](#known-limitations) and
[Reporting feedback](#reporting-feedback) below.

## Requirements

- Docker Engine with the Compose plugin (`docker compose version` prints
  something).
- A domain or hostname you control, pointed at the machine you're
  deploying to, if you want HTTPS via the app's built-in cert flow.
  HTTP-only testing works with `localhost` too.

## 1. Get the release kit

Download and extract the `guard-proxy-release-v0.1.0-beta.2.tar.gz` asset
from the [GitHub Releases page](https://github.com/bihius/guard-proxy/releases),
or copy this `release/` directory if you already have the repository
checked out. You should end up with:

```
guard-proxy-release/
├── docker-compose.yml
├── .env.example
└── haproxy/
    ├── haproxy.cfg
    └── coraza.cfg
```

## 2. Configure

```sh
cd guard-proxy-release
cp .env.example .env
```

Edit `.env` and replace every `change-me` placeholder:

- `GUARD_PROXY_IMAGE_TAG` — pin this to the release you're installing,
  e.g. `v0.1.0-beta.2`. Do not use a mutable tag like `beta` for anything
  you want to reproduce later.
- `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `LOG_INGEST_SHARED_SECRET` —
  generate real secrets, e.g. `openssl rand -hex 32`.
- `CORS_ORIGINS` — the URL(s) you'll open the admin UI from.
- `HAPROXY_HTTP_PORT` / `HAPROXY_HTTPS_PORT` / `FRONTEND_PORT` — adjust if
  80/443/3000 are already in use on the host.

`haproxy/haproxy.cfg` and `haproxy/coraza.cfg` are the seed configuration
HAProxy boots with before you configure anything. Once you apply your
first configuration from the admin UI (see step 4), Guard Proxy generates
and reloads its own HAProxy config from the database — you generally
don't need to hand-edit these files.

## 3. Start the stack

```sh
docker compose up -d
docker compose ps    # wait for all services to report healthy
```

Create the first admin account (idempotent — safe to re-run, it skips if
an admin already exists). Use the `ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars
rather than `--email`/`--password` flags, so the password isn't written to
your shell history:

```sh
docker compose exec \
  -e ADMIN_EMAIL=you@example.com \
  -e ADMIN_PASSWORD='a-strong-password-here' \
  backend /app/.venv/bin/python scripts/seed_admin.py
```

If you set `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `.env` instead, remove them
again after the account is created — they aren't read at container
startup, so leaving them there only leaves a plaintext password at rest.

Log in to the admin UI at `http://<host>:${FRONTEND_PORT:-3000}` (or
through HAProxy on port 80/443, once you've added a vhost — see below).

## 4. Configure your first vhost

In the admin UI: add a vhost pointing at your real origin server, set up
a WAF policy, then use **Apply configuration**. This validates and
generates a new HAProxy config from the database and reloads HAProxy with
it — the static `haproxy.cfg` seed is replaced at that point.

## Upgrading

1. Read the release notes for the target version — note any migration or
   breaking-change callouts.
2. Back up the `pgdata` volume (`docker compose exec postgres pg_dump ...`
   or a volume snapshot) before upgrading, out of caution during beta.
3. Update `GUARD_PROXY_IMAGE_TAG` in `.env` to the new version.
4. `docker compose pull && docker compose up -d`. The backend runs
   `alembic upgrade head` automatically on startup.

## Known limitations

- Beta status: expect bugs; APIs and config formats may still change
  between beta releases.
- No automated upgrade testing between beta versions yet — back up before
  upgrading.
- Single-node only; no HA/clustering.
- DDoS/rate-limit protection ships in a later beta (tracked as issue
  #176) and is not present in this release.

## Reporting feedback

Please file issues on the project's GitHub Issues page, including your
`GUARD_PROXY_IMAGE_TAG`, `docker compose logs <service>` output for the
affected service, and steps to reproduce.
