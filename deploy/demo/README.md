# Guard Proxy demo

This directory starts a self-contained local demo stack:

- Guard Proxy backend, frontend, HAProxy, Coraza, log shipper, PostgreSQL
- two small HTTP echo applications behind HAProxy/Coraza
- a setup script that creates an admin, creates a demo WAF policy, creates
  `app.local` and `api.local` vhosts, and applies runtime config

## Run

```bash
cp deploy/demo/.env.example deploy/demo/.env
git submodule update --init --recursive
chmod +x deploy/demo/setup-demo.sh
./deploy/demo/setup-demo.sh
```

Open the admin panel:

```text
http://localhost:3000
```

The demo exposes the backend directly on `http://localhost:8000` for the admin
panel and setup script. HAProxy listens on `http://localhost:8080` for HTTP WAF
traffic and on `https://localhost:8443` for a temporary self-signed TLS demo.

The TLS bind is intentionally a demo-only patch applied after `/config/apply`.
The next generated config apply can overwrite it.

Default local credentials from `.env.example`:

```text
admin@example.com
GuardProxyDemo12345
```

## Try routing through the WAF

First app:

```bash
curl -i -H 'Host: app.local' 'http://127.0.0.1:8080/hello?name=demo'
```

Expected result: HTTP 200 from `demo-frontend-app`.

Second app:

```bash
curl -i -H 'Host: api.local' 'http://127.0.0.1:8080/v1/status'
```

Expected result: HTTP 200 from `demo-api-service`.

## Trigger a WAF block

This requires the OWASP CRS submodule to be initialized before building the demo.
The setup script checks this and stops early if `configs/coraza/crs/rules` is
missing.

HTTP:

```bash
curl -i -H 'Host: app.local' "http://127.0.0.1:8080/?id=1%27%20OR%20%271%27%3D%271"
```

HTTPS:

```bash
curl -k -i -H 'Host: api.local' "https://127.0.0.1:8443/?id=1%27%20OR%20%271%27%3D%271"
```

Expected result: HTTP 403 from the WAF.

TLS demo:

```bash
curl -k -i -H 'Host: app.local' 'https://127.0.0.1:8443/hello?tls=1'
curl -k -i -H 'Host: api.local' 'https://127.0.0.1:8443/v1/status'
```

## Stop

```bash
docker compose --env-file deploy/demo/.env -f deploy/demo/docker-compose.yml down
```

Remove demo volumes too:

```bash
docker compose --env-file deploy/demo/.env -f deploy/demo/docker-compose.yml down -v
```
