# Coraza SPOA image: ghcr.io/corazawaf/coraza-spoa:0.6.1
# OWASP Core Rule Set: v4.25.0 (pinned via configs/coraza/crs submodule)
FROM busybox:1.37.0-musl AS busybox

FROM ghcr.io/corazawaf/coraza-spoa:0.6.1

COPY --from=busybox /bin/busybox /bin/busybox
COPY configs/coraza/coraza-spoa.yaml /etc/coraza-spoa/coraza-spoa.yaml
COPY configs/coraza/coraza.conf /etc/coraza/coraza.conf
COPY configs/coraza/crs-setup.conf /etc/coraza/crs-setup.conf
COPY configs/coraza/crs /etc/coraza/crs

EXPOSE 9000

ENTRYPOINT ["/coraza-spoa"]
CMD ["-config", "/etc/coraza-spoa/coraza-spoa.yaml"]
