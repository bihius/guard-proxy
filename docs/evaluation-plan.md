# Evaluation Plan — Guard Proxy WAF

**Document status:** methodology contract — written before experiments run.  
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

---

## 2. Hardware and Software Environment

### Test server

| Property       | Value                                                 |
| -------------- | ----------------------------------------------------- |
| Host           | Dell PowerEdge R530 (Proxmox PVE 9.1.1)               |
| CPU            | 2 × Intel Xeon E5-2620 v3 @ 2.40 GHz (24 cores total) |
| RAM            | 128 GiB                  |
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



### Software versions (recorded per run)

Image tags are declared in `benchmarks/lab/docker-compose.targets.yml` and runner scripts. The git SHA and image references of each run are written to `manifest.json` automatically.

---

## 3. Test-Bed Architecture

```
┌─ Lab host ───────────────────────────────────────────────────────────────┐
│                                                                          │
│  ┌─ Test containers ──────┐   ┌─ guard-proxy stack (gp_internal) ─────┐  │
│  │  curl (corpus)         │   │                                       │  │
│  │  go-ftw                ├──►│  HAProxy :80  ──►  Coraza SPOA :9000  │  │
│  │  wrk (load)            │   │                        │              │  │
│  └────────────────────────┘   │               ┌────────┘              │  │
│                               │               ▼                       │  │
│  Host header routes request   │  Target apps (gp_internal):           │  │
│  to the correct vhost:        │    wp.local    → WordPress :80        │  │
│    Host: wp.local             │    ftw.local   → Albedo :8080         │  │
│    Host: ftw.local            └───────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

All test containers and target apps run inside `gp_internal` (Docker bridge). Test containers reach HAProxy at `http://haproxy:80` with the appropriate `Host:` header. HAProxy forwards to the target after SPOE inspection; Coraza fires the CRS ruleset.

Lab source: `benchmarks/lab/`  
Compose overlay: `benchmarks/lab/docker-compose.targets.yml`

---

## 4. Test Targets

| App                        | Purpose                                                                              | Vhost       |
| -------------------------- | ------------------------------------------------------------------------------------ | ----------- |
| **WordPress** 6.x (php8.3) | Real-world CMS — target of the tagged benign/attack corpus (Test 1)                  | `wp.local`  |
| **Albedo** 0.2.0           | CRS go-ftw regression backend (Test 2); answers 200 to everything, so also the load target (Test 3) | `ftw.local` |

WordPress is installed by `make lab-up` (one-shot `wp-cli` container) and runs **without** CRS application exclusion plugins. This is intentional: any false-positive result is reported as an **untuned CRS+WordPress baseline** for the documented policy, not as a universal property of Guard Proxy.

Albedo does no work of its own, so the WAF-vs-direct difference in Test 3 is the cost of HAProxy+Coraza and not of an application.

Each lab vhost has its **own WAF policy**, named after its domain (`Lab wp.local`, `Lab ftw.local`), so tuning one target never changes the other. `make lab-up` creates them with the PL1 profile. A profile (`pl1` or `pl2`, defined in `benchmarks/lab/.env`) is only a set of settings — paranoia level and anomaly thresholds — that `make set-policy POLICY=pl1|pl2` writes into those policies, for both lab vhosts or, with `TARGET_VHOST=<domain>`, for one of them.

The lab was reduced from four targets (Juice Shop, DVWA, WordPress, Albedo) and five scenarios (with OWASP ZAP and Nuclei) to these two targets and three tests: the scanners produced no TP/FN/TN/FP denominator, and Juice Shop crashed under load, which invalidated the overhead measurement. A lab created before this change still has `juice.local`/`dvwa.local` vhosts; delete them (or run `make lab-clean`) before `make lab-up`.

---

## 5. Test Scenarios

Each test answers one question.

| Test | Question                                                         | Tool   | Target      |
| ---- | ---------------------------------------------------------------- | ------ | ----------- |
| 1    | Does the WAF block attacks and let ordinary traffic through?     | curl   | `wp.local`  |
| 2    | Does CRS behave in this integration as the CRS project specifies? | go-ftw | `ftw.local` |
| 3    | What does the WAF cost in latency, throughput, CPU and memory?   | wrk    | `ftw.local` |

### 5.1 Test 1 — Tagged labeled corpus (FP/FN measurement)

**Tool:** curl container + `benchmarks/payloads/`  
**Runner:** `benchmarks/lab/runners/run-corpus.sh`

The corpus has two parts:

- **Benign** (`legitimate.txt`): requests an ordinary visitor or editor of a fresh WordPress sends — pages, search, REST API reads, static assets, a failed login, comments, an admin-ajax heartbeat. Some are deliberately tricky but legitimate: apostrophes in names, SQL words in plain sentences (`select a product from the menu`), a `<code>` snippet in a comment, Polish diacritics.
- **Attacks** (`sqli.txt`, `xss.txt`, `lfi.txt`): every payload is sent twice — in the `s` query parameter and in the body of a POST comment form — so query-string and request-body inspection are both covered.

Every request carries stable correlation headers: `X-GP-Eval-Run`, `X-GP-Eval-Scenario`, and `X-GP-Eval-Case`. The collector matches those headers in the Coraza audit log. Because Coraza uses `SecAuditEngine RelevantOnly`, a correctly allowed benign request may produce no audit event; absence of a tagged blocking event is therefore treated as **allow**. The HTTP status of every request is recorded in `cases.jsonl` as a cross-check.

This is the only source used for TP/FN/TN/FP formulas.

### 5.2 Test 2 — CRS regression suite (go-ftw, log mode)

**Tool:** `ghcr.io/coreruleset/go-ftw:2.6.0`  
**Config:** `benchmarks/lab/scenarios/crs-ftw/config.yaml`  
**Corpus:** `configs/coraza/crs/tests/regression/tests/` (OWASP CRS git submodule)

Each CRS regression test sends a request and lists the rule IDs that must fire (`expect_ids`) or must stay silent (`no_expect_ids`); a few only assert an HTTP status. go-ftw replays the tests through HAProxy to `ftw.local` and checks the rule IDs in the Coraza log. To find the log lines of one test, go-ftw sends a marker request before and after it; lab-only rule 999999 (`benchmarks/lab/coraza/guard-proxy-exceptions.lab.conf`) writes the marker into the log, and the lab overlay tees Coraza's log into `error.log` on the `coraza_audit` volume, which the go-ftw container mounts.

The suite runs in **log mode**, not cloud mode. In cloud mode go-ftw only compares HTTP status codes, and a test that asserts no status passes without any check; an earlier version of this lab reported 99.8 % conformance that way, identical at PL1 and PL2.

Tests that cannot pass in this setup by design are excluded before the run and reported separately:

- rules above the vhost policy's paranoia level (the rule is not loaded);
- response rules (Guard Proxy inspects requests only: `response_check: false`).

Reported: `passed / run` (CRS conformance), split into tests that expect a rule to fire, to stay silent, or another HTTP status, plus the list of failed test IDs. It does **not** estimate TPR/FPR.

### 5.3 Test 3 — Benign load test (latency and RPS overhead)

**Tool:** `elswork/wrk` (arm64+amd64 build of wrk 4.2.0, pinned by digest) with
`benchmarks/lab/scenarios/load/benign-mix.lua`

Two runs against Albedo (`ftw.local`):

1. **Through HAProxy+Coraza** — production WAF path
2. **Direct to the Albedo container** — bypasses HAProxy (`ftw-backend:8080` inside `gp_internal`)

Overhead = WAF_value − direct_value.  
Config: 2 threads, 20 connections, 30-second duration. The mix has 10 requests: 8 GETs (pages, assets, search, API) and 2 POSTs (a form login and a JSON body), because Coraza also inspects request bodies. Albedo answers 200 to all of them, so any non-2xx response through the WAF is a false positive; a run with errors on either path is marked `valid: false` in `performance.json`, because fast 403s would inflate RPS.

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

TP/FN/TN/FP are computed only for labeled, tagged corpus requests (Test 1). go-ftw (Test 2) reports CRS conformance (`passed / run`), split by test expectation.

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

| Metric                              | Guardrail / reporting mode                                   | Source                          |
| ----------------------------------- | ------------------------------------------------------------ | ------------------------------- |
| Corpus TP/FN/TN/FP                  | Reported for the labeled corpus only                         | `benchmarks/payloads/`          |
| CRS conformance (go-ftw)            | Reported, no hard pass/fail threshold                        | CRS regression corpus           |
| Latency overhead p50                | Soft guardrail: ≤ 10 ms (non-functional requirement, thesis) | Project engineering target      |
| Latency overhead p95/p99            | Reported, no hard cap                                        | Informational                   |
| RPS degradation                     | Reported; upper bound, because Albedo does no work           | Informational                   |
| Memory footprint (coraza container) | Reported (no hard cap)                                       | Informational for thesis        |

The run is not declared “successful” or “failed” based on security thresholds. Latency overhead above the guardrail is treated as an engineering finding to investigate, not as a universal product failure. RPS degradation against a backend that answers instantly is close to 100 % by construction: against a real application the same absolute cost per request is a much smaller share of the response time.

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
cp docker/.env.example docker/.env
cp benchmarks/lab/.env.example benchmarks/lab/.env
# Edit both .env files if needed (passwords, ports)
# docker/.env must include ADMIN_EMAIL and ADMIN_PASSWORD for lab seeding.

# 5. Bring up the lab
make lab-up
```

### 8.2 The "One-Click" Evaluation (Recommended)

To run the entire test suite and compare Paranoia Level 1 (PL1) against Paranoia Level 2 (PL2), just run this single command:

```bash
make eval-sweep
```

**What happens when you run this?**
1. The script first writes the **PL1** profile into every lab vhost's policy.
2. It runs the three tests: the tagged corpus on `wp.local`, go-ftw on `ftw.local`, and the wrk load test on `ftw.local`.
3. It saves all metrics for PL1.
4. Then, it automatically writes the **PL2** profile into the same per-vhost policies and repeats all three tests.
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

To move a single target to PL2 while the others stay on PL1 (each vhost has its own policy):

```bash
make set-policy POLICY=pl2 TARGET_VHOST=wp.local
make eval-corpus POLICY=pl2 TARGET_VHOST=wp.local
```

Each runner reads the policy that actually protects its target vhost from the backend API and records it in `summary.json`; it warns when those settings do not match the `POLICY` profile used to label the results directory.

If you need to view results for a specific historical run ID (e.g., if you lost the terminal output), you can use:
```bash
make results RUN_ID=20260610-123456
```
*(Note: Do not append `-pl1` or `-pl2` to the `RUN_ID` here; the Makefile handles that automatically).*
---

## 9. Threats to Validity

### 9.1 Noisy-neighbour CPU contention

The Proxmox host runs a live homelab (media services). CPU pinning (WAF stack + targets to cores 18–20, attacker/load containers to cores 21–23, see `benchmarks/lab/.env.example`) mitigates contention with the host's other workloads, but memory bandwidth and I/O remain shared. **Mitigation:** run during low-traffic hours (early morning); record host load in `manifest.json`; discard outlier runs.

### 9.2 Single-host load generator

The wrk container and the WAF stack run on the same host. The load generator's CPU consumption competes with the WAF. **Effect:** RPS numbers may be pessimistic (load generator throttles before WAF saturates). **Mitigation:** document the single-host topology as a limitation; the relative overhead delta (WAF vs direct) is still valid because both runs share the same load-generator cost.

### 9.3 WordPress false positives without CRS exclusions

WordPress is tested without CRS application exclusion plugins (not yet implemented in the backend). Any false positives are for an **untuned** WAF+CMS combination under a documented policy. They are not generalized to all Guard Proxy deployments.

### 9.4 Small corpus

The tagged corpus has a few dozen benign requests and about a hundred attack requests. TPR and FPR describe this corpus, not attack traffic in general; one case changes the rate by several percentage points.

### 9.5 Lab-specific go-ftw deviations

The lab overrides every CRS test's `Host` header to route it to `ftw.local`, and HAProxy parses and normalizes requests before Coraza sees them. Tests that depend on their own `Host` header or on malformed HTTP that HAProxy rejects or rewrites fail for that reason, not because of a CRS rule. The thesis groups failed test IDs by cause.

---

## 10. Results Format

### summary.json (per scenario)

```json
{
  "run_id": "20260602-141500",
  "scenario": "corpus-<vhost> | ftw | load-<vhost>",
  "target_vhost": "wp.local",
  "policy": {
    "name": "Lab wp.local",
    "paranoia": 1,
    "inbound_threshold": 5,
    "outbound_threshold": 4,
    "mode": "block"
  },
  "detection": {
    "true_positive": 32,
    "false_negative": 2,
    "true_negative": 24,
    "false_positive": 1,
    "tpr": 0.9412,
    "fpr": 0.04,
    "crs_conformance_rate": 0.969,
    "crs_run": 2717,
    "crs_passed": 2633,
    "crs_failed": 84,
    "crs_excluded": 1994
  },
  "performance": {
    "rps": 4120.5,
    "baseline_rps": 5980.0,
    "rps_degradation_pct": 31.1,
    "latency_ms": { "p50": 2.1, "p95": 7.8, "p99": 18.4 },
    "baseline_latency_ms": { "p50": 1.2, "p95": 4.7, "p99": 11.4 },
    "latency_overhead_ms": { "p50": 0.9, "p95": 3.1, "p99": 7.0 },
    "waf_errors": 0,
    "baseline_errors": 0,
    "valid": true
  },
  "resources": {
    "coraza": { "mem_mb_peak": 410, "cpu_pct_avg": 62 },
    "haproxy": { "mem_mb_peak": 95, "cpu_pct_avg": 40 }
  }
}
```

### results.csv

Flat CSV with one row per scenario run. Consumed directly by `thesis/chapters/06-testy.md` tables.

Columns include: `run_id`, `scenario`, `target_vhost`, `policy`, `paranoia_level`, `tpr`, `fpr`, `crs_conformance_rate`, `crs_run`, `crs_passed`, `crs_failed`, `crs_excluded`, `tp`, `fn`, `tn`, `fp`, `corpus_cases`, `waf_blocks_from_log`, `rps_waf`, `rps_direct`, `rps_degradation_pct`, WAF/direct/overhead latency percentiles, `load_valid`, and resource fields.

`policy` is the name of the target vhost's own policy (`Lab <domain>`) and `paranoia_level` its
paranoia level at run time: `1` under the `pl1` profile and `2` under `pl2` — see §8.2 for running both passes.
