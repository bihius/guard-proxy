# Coraza configuration

This directory contains the hand-written M1 Coraza SPOA and OWASP CRS bundle.
M2 will replace these seed files with generated configuration derived from the
policy database.

## First-time setup

The `crs/` directory is a git submodule. If you cloned the repository without
`--recurse-submodules` (or your CI checkout did not initialise submodules), run:

```sh
git submodule update --init --recursive
```

## Pinned versions

- Coraza SPOA image: `ghcr.io/corazawaf/coraza-spoa:0.6.1`
- OWASP Core Rule Set: `v4.25.0`, pinned as the `configs/coraza/crs` git
  submodule

## Files

| File | Purpose |
| --- | --- |
| `coraza-spoa.yaml` | `coraza-spoa` daemon configuration and default application mapping |
| `coraza.conf` | Baseline Coraza directives and CRS includes |
| `crs-setup.conf` | CRS paranoia and anomaly-scoring defaults |
| `crs/` | Pinned OWASP CRS 4.x submodule |

## Defaults

- Request inspection is enabled with `SecRuleEngine On`.
- Response body inspection is disabled for M1, matching ADR-007.
- Blocking paranoia level is `1`.
- Inbound and outbound anomaly thresholds are `5`.
- Relevant audit events are written as JSON to `/var/log/coraza/audit.json`.

## Updating CRS

```sh
git -C configs/coraza/crs fetch --tags
git -C configs/coraza/crs checkout v4.x.y
```

After updating, also change the pinned CRS version in
`deploy/docker/coraza.Dockerfile`, `configs/coraza/crs-setup.conf`, and this
README.
