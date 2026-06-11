# Evaluation Plan — Guard Proxy WAF

**Document status:** methodology contract — written before experiments run.  
**Related chapter:** `thesis/chapters/06-testy.md` (results will be recorded there).  
**Lab source:** `benchmarks/lab/` — all configs, composes, and runner scripts.

---

## 1. Scope

This evaluation assesses guard-proxy as a Web Application Firewall: HAProxy (reverse proxy) with Coraza+OWASP CRS (WAF engine) and a FastAPI control plane that generates HAProxy/Coraza configuration from a policy database.

**In scope:**

- Security effectiveness under documented policy/vhost/corpus configurations.
- False-positive/false-negative analysis on a labeled, tagged benign/attack corpus.
- Performance overhead: latency (p50/p95/p99) and throughput (RPS) compared to direct access.
- Resource consumption (CPU, RAM) of the WAF stack under load.

**Out of scope:**

- Authenticated multi-step attack chains.
- DoS / rate-limiting capabilities.
- Universal WAF detection-rate or false-positive guarantees independent of configuration.
- Per-vhost Coraza plugin configuration (planned for a future milestone).

---

## 2. Hardware and Software Environment

### Test server

| Property       | Value                                                 |
| -------------- | ----------------------------------------------------- |
| Host           | Dell PowerEdge R530 (Proxmox PVE 9.1.1)               |
| CPU            | 2 × Intel Xeon E5-2620 v3 @ 2.40 GHz (24 cores total) |
| RAM            | 128 GiB (32 GiB free at lab time)                     |
| Storage        | ZFS `local-zfs`                                       |
| OS (LXC guest) | Debian 13 (Bookworm) — `debian-13-standard` template  |
| Docker         | Docker Engine ≥ 27.x, Compose V2                      |

**LXC provisioning** (see §8 for full runbook):

```
pct create <VMID> local:vztmpl/debian-13-standard_13.1-2_amd64.tar.zst \
  --hostname guard-proxy-lab \
  --memory 16384 --swap 4096 \
  --cores 6 \
  --storage local-zfs \
  --rootfs local-zfs:60 \
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

Image tags are declared in `benchmarks/lab/docker-compose.targets.yml` and runner scripts. The git SHA and image references of each run are written to `manifest.json` automatically.

---

## 3. Test-Bed Architecture

```
┌─ Proxmox LXC (guard-proxy-lab) ──────────────────────────────────────────┐
│                                                                          │
│  ┌─ Attacker containers ──┐   ┌─ guard-proxy stack (gp_internal) ─────┐  │
│  │  go-ftw                │   │                                       │  │
│  │  OWASP ZAP             ├──►│  HAProxy :80  ──►  Coraza SPOA :9000  │  │
│  │  Nuclei                │   │                        │              │  │
│  │  wrk (load)            │   │               ┌────────┘              │  │
│  └────────────────────────┘   │               ▼                       │  │
│                               │  Target apps (gp_internal):           │  │
│  Host header routes request   │    juice.local → Juice Shop :3000     │  │
│  to the correct vhost:        │    dvwa.local  → DVWA :80             │  │
│    Host: juice.local          │    wp.local    → WordPress :80        │  │
│    Host: dvwa.local           │    ftw.local   → Albedo :8080         │  │
│    Host: wp.local             └───────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

All attacker containers and target apps run inside `gp_internal` (Docker bridge). Attackers reach HAProxy at `http://haproxy:80` with the appropriate `Host:` header. HAProxy forwards to the target after SPOE inspection; Coraza fires the CRS ruleset.

Lab source: `benchmarks/lab/`  
Compose overlay: `benchmarks/lab/docker-compose.targets.yml`

---

## 4. Test Targets

| App                                | Purpose                                                             | Vhost         |
| ---------------------------------- | ------------------------------------------------------------------- | ------------- |
| **OWASP Juice Shop** v17           | Intentionally vulnerable Node.js app — scanner target               | `juice.local` |
| **DVWA** (Damn Vulnerable Web App) | Classic PHP vulnerable app — SQLi/XSS/LFI scenarios                 | `dvwa.local`  |
| **WordPress** 6.x (php8.3)         | Real-world CMS — scanner-assisted coverage and benign corpus target | `wp.local`    |
| **Albedo**                         | CRS go-ftw regression backend compatible with CRS test assumptions  | `ftw.local`   |

WordPress is run **without** CRS application exclusion plugins. This is intentional: any false-positive result is reported as an **untuned CRS+WordPress baseline** for the documented policy, not as a universal property of Guard Proxy.

---

## 5. Test Scenarios

### 5.1 CRS Regression Suite (go-ftw) — CRS conformance

**Tool:** `ghcr.io/coreruleset/go-ftw`  
**Config:** `benchmarks/lab/scenarios/crs-ftw/config.yaml`  
**Corpus:** `configs/coraza/crs/tests/regression/tests/` (OWASP CRS git submodule)

The CRS submodule ships labeled regression tests. go-ftw replays those tests and reports pass/fail test IDs. The runner parses CRS YAML `output.status` values to split tests into expected-block (`403`) and expected-allow (non-`403`) groups, then reports CRS conformance as `passed / run`. It does **not** estimate TPR/FPR.

Target: Albedo (`ftw.local`) as the CRS-compatible backend.

### 5.2 Tagged Labeled Corpus — FP/FN measurement

**Tool:** curl container + `benchmarks/payloads/`
**Runner:** `benchmarks/lab/runners/run-corpus.sh`

The corpus runner sends known-benign paths and known-attack payloads with stable correlation headers: `X-GP-Eval-Run`, `X-GP-Eval-Scenario`, and `X-GP-Eval-Case`. The collector matches those headers in the Coraza audit log. Because Coraza uses `SecAuditEngine RelevantOnly`, a correctly allowed benign request may produce no audit event; absence of a tagged blocking event is therefore treated as **allow**.

This is the only source used for TP/FN/TN/FP formulas.

### 5.3 OWASP ZAP Baseline Scan — scanner-assisted coverage

**Tool:** `ghcr.io/zaproxy/zaproxy` (`zap-baseline.py`)  
**Config:** `benchmarks/lab/scenarios/zap/`

ZAP performs a passive baseline scan of the target application through HAProxy. Its traffic mixes crawler requests, passive checks, and attack-like probes, so it is **not** a clean false-positive-rate source. The evaluation preserves `zap.json` and `zap.html`, counts alerts by risk, and records WAF blocks from tagged audit events as supplemental scanner evidence.

Primary target: **WordPress** (`wp.local`).

### 5.4 Nuclei CVE Templates — reached-app scanner evidence

**Tool:** `projectdiscovery/nuclei`  
**Config:** `benchmarks/lab/scenarios/nuclei/nuclei.yaml`  
**Templates:** `sqli,xss,lfi,rfi,ssrf,injection,traversal,exposure` (severity: medium+)

Nuclei fires known CVE and exposure templates from its curated library. Medium/high/critical findings are treated as reached-app evidence: the template matched an application response. Nuclei is not used to compute TPR because the runner does not have a complete per-template sent-request denominator correlated to WAF decisions.

Target: Juice Shop and DVWA (both known to match many templates).

### 5.5 Benign Load Test — Latency and RPS overhead

**Tool:** `williamyeh/wrk` with `benchmarks/lab/scenarios/load/benign-mix.lua`

Two runs per target:

1. **Through HAProxy+Coraza** — production WAF path
2. **Direct to target container** — bypasses HAProxy (port mapped inside `gp_internal`)

Overhead = WAF_value − direct_value.  
Config: 4 threads, 50 connections, 60-second duration.

---

## 6. Metrics and Definitions

### Security metrics

| Metric                      | Symbol | Formula                            |
| --------------------------- | ------ | ---------------------------------- |
| True Positive Rate (Recall) | TPR    | TP / (TP + FN)                     |
| False Positive Rate         | FPR    | FP / (FP + TN)                     |
| True Positive               | TP     | Attack request correctly blocked   |
| False Negative              | FN     | Attack request incorrectly allowed |
| True Negative               | TN     | Benign request correctly allowed   |
| False Positive              | FP     | Benign request incorrectly blocked |

TP/FN/TN/FP are computed only for labeled, tagged corpus requests. go-ftw reports CRS conformance (`passed / run`) and expected-block/expected-allow pass/fail counts. ZAP and Nuclei are supplemental scanner evidence and do not publish TPR/FPR.

### Performance metrics

| Metric              | Definition                                                                             |
| ------------------- | -------------------------------------------------------------------------------------- |
| p50/p95/p99 latency | 50th/95th/99th percentile of request round-trip time (ms), measured by wrk `--latency` |
| Latency overhead    | Latency(WAF) − Latency(direct) per percentile                                          |
| RPS                 | Requests per second at sustained load                                                  |
| RPS degradation %   | (RPS_direct − RPS_WAF) / RPS_direct × 100                                              |
| Memory peak (MB)    | Peak container memory (`docker stats` / cgroup `memory.peak`) during load              |
| CPU avg %           | Average CPU utilisation during load run                                                |

### Results schema

Each scenario writes `benchmarks/results/run-<RUN_ID>/<scenario>/summary.json`. Aggregated output: `benchmarks/results/run-<RUN_ID>/results.csv` (one row per scenario).

---

## 7. Guardrails and Reporting

Security results are descriptive and configuration-specific. The thesis reports the exact policy, vhost, corpus, and tool for each result. Guard Proxy keeps one soft engineering guardrail for performance because HAProxy/Coraza wiring and generated configuration are project responsibilities.

| Metric                              | Guardrail / reporting mode                    | Source                     |
| ----------------------------------- | --------------------------------------------- | -------------------------- |
| CRS conformance (go-ftw)            | Reported, no hard pass/fail threshold         | CRS regression corpus      |
| Corpus TP/FN/TN/FP                  | Reported for the labeled corpus only          | `benchmarks/payloads/`     |
| ZAP alerts                          | Reported as scanner evidence                  | ZAP baseline report        |
| Nuclei findings                     | Reported as reached-app scanner evidence      | Nuclei JSONL               |
| RPS degradation                     | Soft guardrail: < 20% under this lab workload | Project engineering target |
| Latency overhead p95                | Reported, no hard cap                         | Informational              |
| Memory footprint (coraza container) | Reported (no hard cap)                        | Informational for thesis   |

The run is not declared “successful” or “failed” based on security thresholds. RPS degradation above the guardrail is treated as an engineering finding to investigate, not as a universal product failure.

---

## 8. Run Procedure

### 8.1 First-time setup

On the Proxmox LXC (after provisioning per §2):

```bash
# 0. Install dependencies
apt update && apt install -y git curl

# 1. Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker root

# 2. Clone repo
git clone https://github.com/bihius/guard-proxy.git /opt/guard-proxy
cd /opt/guard-proxy

# 3. Initialise CRS submodule
git submodule update --init --recursive

# 4. Copy env files
cp deploy/docker/.env.example deploy/docker/.env
cp benchmarks/lab/.env.example benchmarks/lab/.env
# Edit both .env files if needed (passwords, ports)
# deploy/docker/.env must include ADMIN_EMAIL and ADMIN_PASSWORD for lab seeding.

# 5. Bring up the lab
make lab-up
```

### 8.2 The "One-Click" Evaluation (Recommended)

To run the entire test suite and compare Paranoia Level 1 (PL1) against Paranoia Level 2 (PL2), just run this single command:

```bash
make eval-sweep
```

**What happens when you run this?**
1. The script first sets Guard Proxy to **PL1**.
2. It attacks the lab using multiple tools (go-ftw, Nuclei, ZAP, and a custom corpus) and runs a performance load test.
3. It saves all metrics for PL1.
4. Then, it automatically switches Guard Proxy to **PL2** and repeats all the attacks and load tests.
5. It saves all metrics for PL2.

**What do you do next?**
When `make eval-sweep` finishes, your results are saved in the `benchmarks/results/` directory as CSV files. 
You can view a clean table of the most recent results by simply running:

```bash
make results
```
This will print a summary of your test run directly in the terminal. You can copy the contents of the generated CSV files into your thesis (`thesis/chapters/06-testy.md`).

### 8.3 Advanced: Manual Runs

If you only want to run a quick smoke test on the default configuration without testing PL2, use:

```bash
make eval-all
```

If you need to view results for a specific historical run ID (e.g., if you lost the terminal output), you can use:
```bash
make results RUN_ID=20260610-123456
```
*(Note: Do not append `-pl1` or `-pl2` to the `RUN_ID` here; the Makefile handles that automatically).*
---

## 9. Threats to Validity



### 9.1 Single-host load generator

The wrk container and the WAF stack run on the same host. The load generator's CPU consumption competes with the WAF. **Effect:** RPS numbers may be pessimistic (load generator throttles before WAF saturates). **Mitigation:** document the single-host topology as a limitation; the relative overhead delta (WAF vs direct) is still valid because both runs share the same load-generator cost.

### 9.2 WordPress false positives without CRS exclusions

WordPress is tested without CRS application exclusion plugins (not yet implemented in the backend). Any false positives are for an **untuned** WAF+CMS combination under a documented policy. They are not generalized to all Guard Proxy deployments.

### 9.3 Scanner denominators

ZAP and Nuclei do not provide clean request-level denominators for WAF TP/FN/TN/FP in the current harness. Their results are reported as scanner evidence, while labeled corpus requests provide the metric denominator.

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
    "true_positive": 32,
    "false_negative": 2,
    "true_negative": 24,
    "false_positive": 1,
    "tpr": 0.9412,
    "fpr": 0.04,
    "crs_conformance_rate": 0.982,
    "crs_passed": 5412,
    "crs_failed": 99
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

Columns include: `run_id`, `scenario`, `target_vhost`, `policy`, `paranoia_level`, `tpr`, `fpr`, `crs_conformance_rate`, `crs_passed`, `crs_failed`, `tp`, `fn`, `tn`, `fp`, `corpus_cases`, `zap_total_alerts`, `nuclei_findings`, `waf_blocks_from_log`, `rps_waf`, `rps_direct`, `rps_degradation_pct`, latency percentiles, and resource fields.

`paranoia_level` is `1` for the baseline (`Lab Baseline`) policy and `2` for the high-paranoia
(`Lab PL2`) policy — see §8.5 for running both passes.
