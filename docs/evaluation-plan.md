# Evaluation Plan — Guard Proxy WAF

**Document status:** methodology contract — written before experiments run.  
**Related chapter:** `thesis/chapters/06-testy.md` (results will be recorded there).  
**Lab source:** `benchmarks/lab/` — all configs, composes, and runner scripts.

---

## 1. Scope

This evaluation assesses guard-proxy as a Web Application Firewall: HAProxy (reverse proxy) with Coraza+OWASP CRS (WAF engine) and a FastAPI control plane that generates HAProxy/Coraza configuration from a policy database.

**In scope:**

- Security effectiveness: detection of SQLi, XSS, LFI/path traversal, and common CVE payloads.
- False positive rate against legitimate CMS traffic (WordPress).
- Performance overhead: latency (p50/p95/p99) and throughput (RPS) compared to direct access.
- Resource consumption (CPU, RAM) of the WAF stack under load.

**Out of scope:**

- Authenticated multi-step attack chains.
- DoS / rate-limiting capabilities.
- Per-vhost Coraza plugin configuration (planned for a future milestone).

---

## 2. Hardware and Software Environment

### Test server

| Property | Value |
|---|---|
| Host | Dell PowerEdge R530 (Proxmox PVE 9.1.1) |
| CPU | 2 × Intel Xeon E5-2620 v3 @ 2.40 GHz (24 cores total) |
| RAM | 125 GiB (32 GiB free at lab time) |
| Storage | ZFS `fast-pool` (~810 GiB free) |
| OS (LXC guest) | Debian 13 (Bookworm) — `debian-13-standard` template |
| Docker | Docker Engine ≥ 27.x, Compose V2 |

**LXC provisioning** (see §8 for full runbook):

```
pct create <VMID> local:vztmpl/debian-13-standard_13.1-2_amd64.tar.zst \
  --hostname guard-proxy-lab \
  --memory 16384 --swap 4096 \
  --cores 6 \
  --storage fast-pool \
  --rootfs fast-pool:60 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --features nesting=1,keyctl=1 \
  --unprivileged 1
```

CPU pinning for reproducibility (add to `/etc/pve/lxc/<VMID>.conf`):

```
lxc.cgroup2.cpuset.cpus: 18-23
```

This dedicates the second-socket tail cores to the lab container, away from the homelab media services running on cores 0–17.

### Noisy-neighbour declaration

The Proxmox host runs ~20 LXC containers (media stack: Jellyfin, \*arr apps, Immich, etc.) with live background traffic. This represents a **shared-tenancy deployment scenario** typical of self-hosted WAF use cases. Each run captures host load average at start time in `results/run-<RUN_ID>/manifest.json`. Runs are repeated three times; the median is reported. Outliers (>2 standard deviations) are discarded.

### Software versions (recorded per run)

All image tags are pinned in `benchmarks/lab/docker-compose.targets.yml` and runner scripts. The git SHA and image digests of each run are written to `manifest.json` automatically.

---

## 3. Test-Bed Architecture

```
┌─ Proxmox LXC (guard-proxy-lab) ────────────────────────────────────────┐
│                                                                          │
│  ┌─ Attacker containers ──┐   ┌─ guard-proxy stack (gp_internal) ────┐  │
│  │  go-ftw                │   │                                       │  │
│  │  OWASP ZAP             ├──►│  HAProxy :80  ──►  Coraza SPOA :9000 │  │
│  │  Nuclei                │   │                        │              │  │
│  │  wrk (load)            │   │               ┌────────┘              │  │
│  └────────────────────────┘   │               ▼                       │  │
│                               │  Target apps (gp_internal):           │  │
│  Host header routes request   │    juice.local → Juice Shop :3000     │  │
│  to the correct vhost:        │    dvwa.local  → DVWA :80             │  │
│    Host: juice.local          │    wp.local    → WordPress :80        │  │
│    Host: dvwa.local           │    app.local   → demo-app :8080       │  │
│    Host: wp.local             └───────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

All attacker containers and target apps run inside `gp_internal` (Docker bridge). Attackers reach HAProxy at `http://haproxy:80` with the appropriate `Host:` header. HAProxy forwards to the target after SPOE inspection; Coraza fires the CRS ruleset.

Lab source: `benchmarks/lab/`  
Compose overlay: `benchmarks/lab/docker-compose.targets.yml`

---

## 4. Test Targets

| App | Purpose | Vhost |
|---|---|---|
| **OWASP Juice Shop** v17 | Intentionally vulnerable Node.js app — primary TPR target | `juice.local` |
| **DVWA** (Damn Vulnerable Web App) | Classic PHP vulnerable app — SQLi/XSS/LFI scenarios | `dvwa.local` |
| **WordPress** 6.x (php8.3) | Real-world CMS — primary **FPR target** (no CRS exclusions) | `wp.local` |
| **demo-app** (echo server) | Existing minimal target — smoke check | `app.local` |

WordPress is run **without** CRS application exclusion plugins. This is intentional: the false positive rate against an untuned CRS+WP configuration is itself a finding, and per-vhost exclusion support is not yet implemented in the backend. The comparison will be revisited once per-vhost Coraza configuration lands.

---

## 5. Test Scenarios

### 5.1 CRS Regression Suite (go-ftw) — TPR gold standard

**Tool:** `ghcr.io/coreruleset/go-ftw`  
**Config:** `benchmarks/lab/scenarios/crs-ftw/config.yaml`  
**Corpus:** `configs/coraza/crs/tests/regression/tests/` (OWASP CRS git submodule)

The CRS submodule ships labeled test cases — each test case specifies whether the WAF **should** block or **should** pass the request. go-ftw replays all cases and reports pass/fail per rule. This is the most authoritative TPR measurement because the corpus was written by the same team that wrote the rules.

Targets: Juice Shop (`juice.local`) as the default routing vhost.

### 5.2 OWASP ZAP Baseline Scan — FPR measurement

**Tool:** `ghcr.io/zaproxy/zaproxy` (`zap-baseline.py`)  
**Config:** `benchmarks/lab/scenarios/zap/`

ZAP performs a passive + light active scan of the target application through HAProxy. The scan uses legitimate-looking probes and crafted attack requests. ZAP alerts with Medium/High risk are WAF-relevant; the WAF's response (block or pass) per alert category provides the FPR signal on real application traffic.

Primary target: **WordPress** (`wp.local`) — the richest source of false positive measurements because a real CMS has complex, diverse traffic patterns.

### 5.3 Nuclei CVE Templates — CVE TPR

**Tool:** `projectdiscovery/nuclei`  
**Config:** `benchmarks/lab/scenarios/nuclei/nuclei.yaml`  
**Templates:** `sqli,xss,lfi,rfi,ssrf,injection,traversal,exposure` (severity: medium+)

Nuclei fires known CVE and exposure payloads from its curated template library. Each finding that reaches the target app is a potential WAF false negative; cross-referenced against the Coraza audit log in `collect-metrics.sh`.

Target: Juice Shop and DVWA (both known to match many templates).

### 5.4 Benign Load Test — Latency and RPS overhead

**Tool:** `williamyeh/wrk` with `benchmarks/lab/scenarios/load/benign-mix.lua`

Two runs per target:

1. **Through HAProxy+Coraza** — production WAF path
2. **Direct to target container** — bypasses HAProxy (port mapped inside `gp_internal`)

Overhead = WAF_value − direct_value.  
Config: 4 threads, 50 connections, 60-second duration.

---

## 6. Metrics and Definitions

### Security metrics

| Metric | Symbol | Formula |
|---|---|---|
| True Positive Rate (Recall) | TPR | TP / (TP + FN) |
| False Positive Rate | FPR | FP / (FP + TN) |
| True Positive | TP | Attack request correctly blocked |
| False Negative | FN | Attack request incorrectly allowed |
| True Negative | TN | Benign request correctly allowed |
| False Positive | FP | Benign request incorrectly blocked |

For go-ftw: TP/FN/TN/FP come directly from labeled test case outcomes.  
For ZAP/Nuclei: WAF blocks are identified from the Coraza audit log (JSON lines with `response.status == 403`); unblocked attack requests are FN candidates.

### Performance metrics

| Metric | Definition |
|---|---|
| p50/p95/p99 latency | 50th/95th/99th percentile of request round-trip time (ms), measured by wrk `--latency` |
| Latency overhead | Latency(WAF) − Latency(direct) per percentile |
| RPS | Requests per second at sustained load |
| RPS degradation % | (RPS_direct − RPS_WAF) / RPS_direct × 100 |
| Memory peak (MB) | Peak container memory (`docker stats` / cgroup `memory.peak`) during load |
| CPU avg % | Average CPU utilisation during load run |

### Results schema

Each scenario writes `benchmarks/results/run-<RUN_ID>/<scenario>/summary.json`. Aggregated output: `benchmarks/results/run-<RUN_ID>/results.csv` (one row per scenario).

---

## 7. Success Criteria

> **Note:** The thresholds below are proposed defaults derived from `README.testing.md` and common WAF benchmarks. Confirm with the thesis supervisor before the final evaluation run.

| Metric | Target | Source |
|---|---|---|
| TPR (go-ftw CRS corpus) | ≥ 95% | CRS project target; README.testing.md |
| FPR on benign traffic (ZAP on WordPress) | < 10% | README.testing.md |
| RPS degradation | < 20% | README.testing.md |
| Latency overhead p95 | ≤ 50 ms | Common WAF SLA baseline |
| Memory footprint (coraza container) | Reported (no hard cap) | Informational for thesis |

A run is considered **successful** if TPR ≥ 95% and FPR < 10% and RPS degradation < 20%. Latency overhead is reported regardless. Resource usage is informational.

---

## 8. Run Procedure

### 8.1 First-time setup

On the Proxmox LXC (after provisioning per §2):

```bash
# 1. Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker root

# 2. Clone repo
git clone https://github.com/bihius/guard-proxy.git /opt/guard-proxy
cd /opt/guard-proxy

# 3. Initialise CRS submodule
git submodule update --init --recursive

# 4. Copy env files
cp deploy/demo/.env.example deploy/demo/.env
cp benchmarks/lab/.env.example benchmarks/lab/.env
# Edit both .env files if needed (passwords, ports)

# 5. Bring up the lab
make eval-up
```

### 8.2 Running the evaluation

```bash
cd /opt/guard-proxy

# Single pass (for smoke check):
make eval-all

# Three passes for thesis (median of three):
for i in 1 2 3; do
  RUN_ID=$(date +%Y%m%d-%H%M%S) make eval-all
  sleep 60  # brief pause between runs
done

# View results summary:
make eval-results
```

### 8.3 Changing target vhost

```bash
# Run ZAP against WordPress (best FPR target):
make eval-zap TARGET_VHOST=wp.local

# Run load test against DVWA:
make eval-load TARGET_VHOST=dvwa.local DIRECT_HOST=dvwa DIRECT_PORT=80
```

### 8.4 Collecting results for the thesis

After runs complete:

```bash
# Aggregate to CSV:
RUN_ID=<id> make eval-metrics

# Copy curated results to thesis:
cp benchmarks/results/run-<id>/results.csv thesis/assets/figures/eval-results-<id>.csv
```

---

## 9. Threats to Validity

### 9.1 Noisy-neighbour CPU contention

The Proxmox host runs a live homelab (media services). CPU pinning to cores 18–23 mitigates this, but memory bandwidth and I/O remain shared. **Mitigation:** run during low-traffic hours (early morning); record host load in `manifest.json`; discard outlier runs.

### 9.2 Single-host load generator

The wrk container and the WAF stack run on the same host. The load generator's CPU consumption competes with the WAF. **Effect:** RPS numbers may be pessimistic (load generator throttles before WAF saturates). **Mitigation:** document the single-host topology as a limitation; the relative overhead delta (WAF vs direct) is still valid because both runs share the same load-generator cost.

### 9.3 WordPress false positives without CRS exclusions

WordPress is tested without CRS application exclusion plugins (not yet implemented in the backend). The reported FPR against WordPress is for an **untuned** WAF+CMS combination. This is explicitly documented as a finding. The expected FPR will decrease once per-vhost Coraza configuration supports exclusion plugins.

### 9.4 go-ftw TP/FP split approximation

go-ftw v1.x reports aggregate pass/fail counts, not per-case attack/benign labels. The TP/FP split uses an estimated attack ratio (85%). Rerunning with go-ftw v2 `--output json-per-test` provides the exact split.

---

## 10. Results Format

### summary.json (per scenario)

```json
{
  "run_id": "20260602-141500",
  "scenario": "ftw | zap-<vhost> | nuclei-<vhost> | load-<vhost>",
  "target_vhost": "juice.local",
  "policy": {
    "name": "Lab Baseline",
    "paranoia": 1,
    "inbound_threshold": 5,
    "mode": "block"
  },
  "detection": {
    "true_positive": 312,
    "false_negative": 18,
    "true_negative": 140,
    "false_positive": 4,
    "tpr": 0.945,
    "fpr": 0.028
  },
  "performance": {
    "rps": 4120.5,
    "baseline_rps": 5980.0,
    "rps_degradation_pct": 31.1,
    "latency_ms": { "p50": 2.1, "p95": 7.8, "p99": 18.4 },
    "latency_overhead_ms": { "p50": 0.9, "p95": 3.1, "p99": 7.0 }
  },
  "resources": {
    "coraza": { "mem_mb_peak": 410, "cpu_pct_avg": 62 },
    "haproxy": { "mem_mb_peak": 95, "cpu_pct_avg": 40 }
  }
}
```

### results.csv

Flat CSV with one row per scenario run. Consumed directly by `thesis/chapters/06-testy.md` tables.

Columns: `run_id`, `scenario`, `target_vhost`, `policy`, `tpr`, `fpr`, `tp`, `fn`, `tn`, `fp`, `waf_blocks_from_log`, `rps_waf`, `rps_direct`, `rps_degradation_pct`, `lat_p50_ms`, `lat_p95_ms`, `lat_p99_ms`, `lat_oh_p50_ms`, `lat_oh_p95_ms`, `lat_oh_p99_ms`, `coraza_mem_mb_peak`, `coraza_cpu_pct_avg`, `haproxy_mem_mb_peak`, `haproxy_cpu_pct_avg`.
