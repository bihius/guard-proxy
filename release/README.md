# Guard Proxy — beta install guide

This release kit runs Guard Proxy from prebuilt images published to GHCR.
It does not require cloning the source repository or building anything
locally.

**Beta status.** This is a beta build for early testers. Expect
rough edges. Generated configs, the GeoIP database and PostgreSQL data all
live in Docker volumes, but no upgrade-path guarantees are made between beta
releases yet — back up `pgdata` before upgrading. See
[What an upgrade does not carry over](#what-an-upgrade-does-not-carry-over)
for what is kept off the volumes, then
[Known limitations](#known-limitations) and
[Reporting feedback](#reporting-feedback) below.

## Requirements

- Docker Engine with the Compose plugin (`docker compose version` prints
  something).
- A `linux/amd64` or `linux/arm64` host: the published images are multi-arch,
  so Apple Silicon and ARM servers run the stack natively. Another
  architecture has no image and `docker compose pull` stops with
  `no matching manifest for <arch>`; run Compose with
  `DOCKER_DEFAULT_PLATFORM=linux/amd64` there, which runs the stack under
  emulation — noticeably slower, fine for evaluating.
- A domain or hostname you control, pointed at the machine you're
  deploying to, if you want HTTPS via the app's built-in cert flow.
  HTTP-only testing works with `localhost` too.

## 1. Get the release kit

Download and extract the `guard-proxy-release-v0.1.0-beta.10.tar.gz` asset
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
  e.g. `v0.1.0-beta.10`. Do not use a mutable tag like `beta` or `latest` for
  anything you want to reproduce later: both follow the newest beta release.
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

Pick a real address here: this email also becomes the ACME contact for the
built-in certificate flow, and Let's Encrypt rejects reserved domains such as
`example.com`. Leaving the placeholder in place makes every certificate
request fail with `The ACME server believes ... is an invalid email
address`.

Log in to the admin UI at `http://<host>:${FRONTEND_PORT:-3000}` (or
through HAProxy on port 80/443, once you've added a vhost — see below).

The UI container serves the built app from nginx and forwards `/api/v1` to
the backend, so the panel and the API share an origin. That port is plain
HTTP: put it behind TLS (your own reverse proxy, or a Guard Proxy vhost)
before exposing it outside a trusted network, and set
`AUTH_REFRESH_COOKIE_SECURE=true` in `.env` once you do, so the refresh
cookie is only sent over HTTPS.

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

### What an upgrade does not carry over

Everything you configure in the admin UI survives an upgrade: it lives in
PostgreSQL and is re-rendered onto the `generated_config` volume (which also
holds the GeoIP database and the vhost certificates), so vhosts, policies and
HTTPS keep working. Two things are stored outside the volumes:

- **Bans and rate-limit counters.** These are HAProxy stick-tables, held in
  the HAProxy process's memory and never written to disk. The generated config
  wires them to a `peers` section, and **Apply configuration** waits until the
  worker it is about to replace is able to hand them over before reloading, so
  a ban is not lifted just because an admin changed something. A tag-only
  upgrade leaves the pinned `haproxy` container running, so they survive that
  too — except on the **first** Apply after coming from v0.1.0-beta.8 or older:
  the worker running at that point predates the `peers` section and cannot
  teach it anything. Every later Apply carries them over, and an upgrade from
  v0.1.0-beta.9 already generates the section, so it keeps them on the first
  Apply as well. A restarted or recreated HAProxy container starts empty, and
  nothing can recover that. See the DDoS Protection & Auto-Ban section of
  `docs/architecture.md`.
- **Certbot's ACME account key and renewal configuration.** The built-in
  certificate flow runs certbot inside the `backend` container with its
  configuration under `/tmp`, which is not a volume, so the account is
  re-registered on the next renewal instead of being reused. The issued
  certificate itself is stored in the database and on `generated_config`, so
  sites keep serving their existing certificate throughout the upgrade.

### v0.1.0-beta.10

- **Bans and rate counters now survive every Apply configuration.**
  v0.1.0-beta.9 wired the DDoS stick-tables to an HAProxy `peers` section, but
  HAProxy only starts the handover of those tables when the worker being
  replaced has finished its own resync — up to five seconds after that worker
  started. An Apply that arrived inside that window dropped every ban and
  counter, silently and without a log line, and an Apply issued right after a
  ban was created was the most reliable way to lose it. The backend now waits
  for the outgoing worker before asking HAProxy to reload (bounded by those
  five seconds, and free when the worker has nothing to wait for). On the
  v0.1.0-beta.8 → v0.1.0-beta.9 upgrade path, which lost the ban in 5 of 8
  applies, a rapid Apply loop now keeps it 21 times out of 21; a fresh install
  keeps it 20 out of 20. The DDoS Protection & Auto-Ban section of
  `docs/architecture.md` describes the mechanism.
- **Two cases still start the tables empty**, and this release does not change
  either:
  - the **first** Apply after upgrading from v0.1.0-beta.8 or older: the worker
    being replaced was started from a config with no `peers` section and cannot
    teach anything. Every Apply after that one carries the tables over, and an
    upgrade from v0.1.0-beta.9 — which already generates the section — keeps
    them on the first Apply too;
  - a **restarted or recreated `haproxy` container**: there is no predecessor
    left to synchronize from.
- **`docker-compose.yml` and the seed `haproxy/*.cfg` are unchanged from
  v0.1.0-beta.9**, so changing `GUARD_PROXY_IMAGE_TAG` and running the steps
  above is enough; extract the new kit only if you want the updated
  `.env.example` and this guide.
- **Database migrations:** none added since v0.1.0-beta.9. Back up `pgdata`
  first anyway, as in the steps above.

### v0.1.0-beta.9

- **The images are multi-arch now.** Both `linux/amd64` and `linux/arm64` are
  published, so an Apple Silicon or ARM host pulls and runs the stack
  natively: drop `DOCKER_DEFAULT_PLATFORM=linux/amd64` from your Compose
  commands if you had set it for the `no matching manifest` error. Tags
  published before this release stay `linux/amd64` only, so that workaround is
  still the way to run, for example, v0.1.0-beta.8 on ARM.
- **`beta` and `latest` follow the newest beta.** This release is published as
  a normal GitHub release rather than a prerelease, and updates `latest` with
  `beta`. Keep pinning `GUARD_PROXY_IMAGE_TAG` to a version if you want to
  reproduce a deployment.
- **Bans and rate counters survive Apply configuration.** The generated config
  now wires the DDoS stick-tables to an HAProxy `peers` section, so applying a
  change no longer lifts a ban. Two exceptions, both described in
  [What an upgrade does not carry over](#what-an-upgrade-does-not-carry-over):
  the **first** Apply after this upgrade still starts the tables empty (the
  worker being replaced was started from a config that had no such section),
  and a restarted or recreated HAProxy container always starts empty.
- **`ACME_SERVER_URL` (optional) points the certificate flow at another ACME
  directory** — Let's Encrypt staging, or a local server such as Pebble — so
  issuance can be exercised without spending production rate limits. Leave it
  unset for Let's Encrypt production. Trusting the certificate authority of
  such a server needs no Guard Proxy setting: export `REQUESTS_CA_BUNDLE` with
  its PEM file and certbot reads it. See `.env.example`.
- **`docker-compose.yml` and the seed `haproxy/*.cfg` are unchanged from
  v0.1.0-beta.8**, so changing `GUARD_PROXY_IMAGE_TAG` and running the steps
  above is enough; extract the new kit only if you want the updated
  `.env.example` and this guide.
- **Database migrations:** none added since v0.1.0-beta.8. Back up `pgdata`
  first anyway, as in the steps above.

### v0.1.0-beta.8

- **No new configuration.** `.env` needs no new variables, and
  `docker-compose.yml`, `haproxy/*.cfg` and the `coraza` setup are unchanged
  from v0.1.0-beta.7. Changing `GUARD_PROXY_IMAGE_TAG` and running the steps
  above is enough.
- **Database migrations:** none added since v0.1.0-beta.7. Back up `pgdata`
  first anyway, as in the steps above.

### v0.1.0-beta.7

- **Use the new release kit, don't just change the tag.** This release
  changes `docker-compose.yml` (the frontend container now serves the built
  UI from nginx on container port 8080, and the `coraza` service gets a
  writable `coraza_status` volume at
  `/var/lib/guard-proxy/generated/coraza-status`) and the seed
  `haproxy/*.cfg`. Extract the new kit, keep your `.env`, and copy your
  `haproxy/` files only if you edited them by hand. A stack that keeps the
  old Compose file still proxies traffic through HAProxy, but the admin UI
  and the API become unreachable: the old file publishes and health-checks
  the frontend container's old port 5173 while the new frontend image
  serves nginx on 8080, so the container never reports healthy. Coraza rule
  changes then also fail **Apply configuration** (the apply waits out
  `CORAZA_RELOAD_TIMEOUT_SECONDS` and rolls back).
- **Upgrade `backend` and `coraza` together.** They are published from one
  tag; pinning them to different versions leaves the backend waiting for a
  reload status the older Coraza image never writes, so every apply rolls
  back. Leave `GUARD_PROXY_IMAGE_TAG` as the single knob.
- **Secrets must be at least 32 characters and must differ.** The backend
  now refuses to start while `JWT_SECRET_KEY` or
  `LOG_INGEST_SHARED_SECRET` is shorter than 32 characters, is the
  placeholder shipped in `.env.example`, or holds the same value as the
  other one. Generate both with `openssl rand -hex 32` and update `.env`
  before upgrading.
- **If the UI is reached over HTTPS, set
  `AUTH_REFRESH_COOKIE_SECURE=true`.** The backend logs a startup warning
  while it is false; without it the long-lived refresh cookie travels in
  clear text.
- **Audit log size.** `CORAZA_AUDIT_LOG_MAX_BYTES` (default `268435456`,
  256 MiB) now comes from `.env` as well as the image. The supervisor
  truncates `audit.log` in place once it passes the cap and keeps one
  `audit.log.1`, so size the `coraza_audit` volume for both copies.
- **Fix rows the stricter validation now rejects.** A vhost whose domain is
  not a valid hostname, or a custom rule or rule exclusion whose value ends
  with a newline, is rejected when saved and blocks every apply until it is
  corrected.

## Known limitations

- Beta status: expect bugs; APIs and config formats may still change
  between beta releases.
- No automated upgrade testing between beta versions yet — back up before
  upgrading.
- Single-node only; no HA/clustering.
- Every vhost has its own WAF policy, and each distinct policy in use runs
  as a separate Coraza instance (about 6–10 MiB extra memory per policy).
  Path-scoped policy bindings to a different policy than the vhost's own
  are not supported; **Apply configuration** explains and refuses them.

## Reporting feedback

Please file issues on the project's GitHub Issues page, including your
`GUARD_PROXY_IMAGE_TAG`, `docker compose logs <service>` output for the
affected service, and steps to reproduce.
