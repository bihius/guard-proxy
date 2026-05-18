# Coraza SPOA image: ghcr.io/corazawaf/coraza-spoa:0.6.1
# OWASP Core Rule Set: v4.25.0 (pinned via configs/coraza/crs submodule)
FROM ghcr.io/corazawaf/coraza-spoa:0.6.1 AS upstream

FROM alpine:3.19

RUN apk add --no-cache inotify-tools tini

COPY --from=upstream /coraza-spoa /usr/local/bin/coraza-spoa
COPY configs/coraza/coraza-spoa.yaml /etc/coraza-spoa/coraza-spoa.yaml
COPY configs/coraza/coraza.conf /etc/coraza/coraza.conf
COPY configs/coraza/crs-setup.conf /etc/coraza/crs-setup.conf
COPY configs/coraza/crs /etc/coraza/crs
COPY deploy/docker/coraza-supervisor.sh /usr/local/bin/coraza-supervisor

RUN chmod +x /usr/local/bin/coraza-supervisor \
    && /usr/local/bin/coraza-spoa -h >/dev/null 2>&1 || true

EXPOSE 9000

ENTRYPOINT ["/sbin/tini", "--", "/usr/local/bin/coraza-supervisor"]
