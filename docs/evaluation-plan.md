# Evaluation Plan — Guard Proxy WAF

**Document status:** methodology contract — written before experiments run.  
**Lab source:** `benchmarks/lab/` — all configs, composes, and runner scripts.

---

## 1. Scope

This evaluation assesses guard-proxy as a Web Application Firewall: HAProxy (reverse proxy) with Coraza+OWASP CRS (WAF engine) and a FastAPI control plane that generates HAProxy/Coraza configuration from a policy database.

**In scope:**

- Security effectiveness under documented policy/vhost/corpus configurations.
- False-positive/false-negative analysis on a labeled, tagged benign/attack corpus.
- Conformance of the CRS integration with the CRS project's own regression tests.
- Performance overhead: latency (p50/p95/p99) and throughput (RPS) compared to direct access.
- Resource consumption (CPU, RAM) of the WAF stack under load.

**Out of scope:**

- Authenticated multi-step attack chains.
- DoS / rate-limiting capabilities (rate limiting is off in both lab profiles).
- Universal WAF detection-rate or false-positive guarantees independent of configuration.

---

## 2. Hardware and Software Environment

The lab uses two hosts connected by a WireGuard VPN:

| Host        | Thesis lab address | Role                                                        |
| ----------- | ------------------ | ----------------------------------------------------------- |
| Lab server  | `10.99.99.20`      | Guard Proxy stack, targets, curl corpus, go-ftw             |
| Load client | `10.99.99.30`      | native `wrk` only, started by hand                          |

The server's address is the only one the lab needs: set it as `LAB_SERVER_ADDR` in `benchmarks/lab/.env`. Albedo's direct port is published on it, and the load test builds the wrk URLs from it.

### Lab server

| Property | Value                                         |
| -------- | --------------------------------------------- |
| Host     | Dell OptiPlex 3070 (`slayer`)                 |
| CPU      | Intel Core i5-9500 @ 3.00 GHz (6 cores)       |
| RAM      | 16 GB                                         |
| OS       | Debian 13 (trixie)                            |
| Runtime  | Docker Engine, Docker Compose V2              |

### Load client

| Property | Value                                      |
| -------- | ------------------------------------------ |
| Host     | Mac mini (Apple M4, 16 GB)                 |
| Tool     | native `wrk` 4.2.0 (Homebrew)              |
| Access   | none: wrk is started by hand; its output is pasted into the server terminal |

### Software versions (recorded per run)

Image tags are declared in `benchmarks/lab/docker-compose.targets.yml` and the runner scripts. The CRS submodule is pinned at v4.25.0. Each run writes the git SHA, host CPU/RAM and load average to `manifest.json`; the load test also records the load mode and both URLs in `performance.json`. Record the client's `wrk -v` output in the thesis, because a manual run cannot read it.

---

## 3. Test-Bed Architecture

```
┌─ Lab server (LAB_SERVER_ADDR, 10.99.99.20) ──────────────────────────────┐
│                                                                          │
│  ┌─ Test containers ──────┐   ┌─ guard-proxy stack (gp_internal) ─────┐  │
│  │  curl (corpus)         ├──►│  HAProxy :80  ──►  Coraza SPOA :9000  │  │
│  │  go-ftw (CRS tests)    │   │                        │              │  │
│  └────────────────────────┘   │               ┌────────┘              │  │
│                               │               ▼                       │  │
│                               │  Target apps (gp_internal):           │  │
│                               │    wp.local  → WordPress :80          │  │
│                               │    ftw.local → Albedo :8080           │  │
│                               └───────────────────────────────────────┘  │
│  Published ports on LAB_SERVER_ADDR:                                     │
│    HAPROXY_HTTP_PORT → HAProxy (WAF path)                                │
│    LAB_FTW_DIRECT_PORT (18080) → Albedo (direct path, no WAF)            │
└──────────────────────────────▲───────────────────────────────────────────┘
                               │ HTTP over the VPN (both paths)
┌─ Load client (10.99.99.30) ──┴───────────────────────────────────────────┐
│  native wrk + benign-mix.lua, started by hand with the printed command   │
└──────────────────────────────────────────────────────────────────────────┘
```

The corpus (curl) and go-ftw containers attach to `gp_internal` and reach HAProxy at `http://haproxy:80` with the target's `Host:` header. Only `wrk` runs on the separate client, and nothing on the server connects to it: for each run, `run-load.sh` prints the exact `wrk` command, the operator starts it on the client, and pastes wrk's output back into the server terminal. The measured HTTP traffic goes from the client to `LAB_SERVER_ADDR` directly, for the WAF path and for the direct path alike.

Without `LOAD_CLIENT=manual`, `run-load.sh` runs `wrk` in a container on the server instead (single-machine mode, used for smoke runs).

Lab source: `benchmarks/lab/`  
Compose overlay: `benchmarks/lab/docker-compose.targets.yml`

---

## 4. Test Targets and Policies

| App                        | Purpose                                                                              | Vhost       |
| -------------------------- | ------------------------------------------------------------------------------------ | ----------- |
| **WordPress** (php8.3)     | Real-world CMS — target of the tagged benign/attack corpus (Test 1)                  | `wp.local`  |
| **Albedo** 0.2.0           | CRS go-ftw regression backend (Test 2); answers 200 to everything, so also the load target (Test 3) | `ftw.local` |

WordPress is installed by `make lab-up` (one-shot `wp-cli` container) and runs **without** CRS application exclusion plugins. This is intentional: any false-positive result is reported as an **untuned CRS+WordPress baseline** for the documented policy, not as a universal property of Guard Proxy.

Albedo does no work of its own, so the WAF-vs-direct difference in Test 3 is the cost of HAProxy+Coraza and not of an application.

Each lab vhost has its **own WAF policy**, named after its domain (`Lab wp.local`, `Lab ftw.local`). `make set-policy POLICY=pl1|pl2` writes one of two fixed profiles into those policies:

| Profile | Paranoia | Inbound threshold | Outbound threshold | Mode    | Rate limiting | GeoIP | Exclusions |
| ------- | -------- | ----------------- | ------------------ | ------- | ------------- | ----- | ---------- |
| `pl1`   | 1        | 5                 | 4                  | `block` | off           | off   | none       |
| `pl2`   | 2        | 5                 | 4                  | `block` | off           | off   | none       |

The profiles differ **only** in paranoia level, so a PL1 vs PL2 difference is attributable to it. They are fixed in `benchmarks/lab/policy-profiles.sh`. `set-policy` refuses to run when `benchmarks/lab/.env` still sets `LAB_POLICY_*` / `LAB_PL2_POLICY_*` to other values, and when a lab policy has rule exclusions, rule overrides or custom rules. It then reads the policy back from the API and checks every profile field.

---

## 5. Test Scenarios

Each test answers one question.

| Test | Question                                                         | Tool   | Runs on     | Target      |
| ---- | ---------------------------------------------------------------- | ------ | ----------- | ----------- |
| 1    | Does the WAF block attacks and let ordinary traffic through?     | curl   | lab server  | `wp.local`  |
| 2    | Does CRS behave in this integration as the CRS project specifies? | go-ftw | lab server  | `ftw.local` |
| 3    | What does the WAF cost in latency, throughput, CPU and memory?   | wrk    | load client | `ftw.local` |

### 5.1 Test 1 — Tagged labeled corpus (FP/FN measurement)

**Tool:** curl container + `benchmarks/payloads/`  
**Runner:** `benchmarks/lab/runners/run-corpus.sh`

The corpus has 139 cases:

| Part    | Source                                  | Requests                                           | Cases |
| ------- | --------------------------------------- | -------------------------------------------------- | ----- |
| Benign  | `legitimate.txt`                        | 31 GET, 7 POST form, 1 POST JSON                   | 39    |
| SQLi    | `sqli.txt` (19 payloads)                | each as `GET /?s=<payload>` and as POST comment form | 38  |
| XSS     | `xss.txt` (13 payloads)                 | each as `GET /?s=<payload>` and as POST comment form | 26  |
| LFI     | `lfi.txt` (18 payloads)                 | each as `GET /?s=<payload>` and as POST comment form | 36  |

- **Benign** requests are what an ordinary visitor or editor of a fresh WordPress sends — pages, search, REST API reads, static assets, a failed login, comments (form and REST JSON), an admin-ajax heartbeat. Some are deliberately tricky but legitimate: apostrophes in names, SQL words in plain sentences (`select a product from the menu`), a `<code>` snippet in a comment, Polish diacritics.
- **Attacks** are sent twice: in the `s` query parameter and in the `comment` field of `POST /wp-comments-post.php`, so query-string and request-body inspection are both covered.

Every request carries stable correlation headers: `X-GP-Eval-Run`, `X-GP-Eval-Scenario`, and `X-GP-Eval-Case`. The collector matches those headers in the Coraza audit log. Because Coraza uses `SecAuditEngine RelevantOnly`, a correctly allowed benign request may produce no audit event; absence of a tagged blocking event is therefore treated as **allow**. The HTTP status of every request is recorded in `cases.jsonl` as a cross-check.

This is the only source used for TP/FN/TN/FP formulas.

### 5.2 Test 2 — CRS regression suite (go-ftw, log mode)

**Tool:** `ghcr.io/coreruleset/go-ftw:2.6.0`  
**Config:** `benchmarks/lab/scenarios/crs-ftw/config.yaml`  
**Corpus:** `configs/coraza/crs/tests/regression/tests/` (OWASP CRS v4.25.0 git submodule)

Each CRS regression test sends a request and lists the rule IDs that must fire (`expect_ids`) or must stay silent (`no_expect_ids`); a few only assert an HTTP status. go-ftw replays the tests through HAProxy to `ftw.local` and checks the rule IDs in the Coraza log. To find the log lines of one test, go-ftw sends a marker request (header `X-GP-FTW-Marker`) before and after it; lab-only rule 999999 (`benchmarks/lab/coraza/guard-proxy-exceptions.lab.conf`) writes the marker into the log, and the lab overlay tees Coraza's log into `/var/log/coraza/error.log` on the `coraza_audit` volume, which the go-ftw container mounts read-only.

The suite runs in **log mode**, never in cloud mode. In cloud mode go-ftw only compares HTTP status codes, and a test that asserts no status passes without any check; an earlier version of this lab reported 99.8 % conformance that way, identical at PL1 and PL2, with 4645 of 4674 tests unchecked.

Tests that cannot pass in this setup by design are excluded before the run and reported separately:

- rules above the vhost policy's paranoia level (the rule is not loaded);
- response rules (Guard Proxy inspects requests only: `response_check: false`).

Reported: `passed / run` (CRS conformance), split into tests that expect a rule to fire, to stay silent, or another HTTP status, plus the list of failed test IDs. It does **not** estimate TPR/FPR.

### 5.3 Test 3 — Benign load test (latency and RPS overhead)

**Tool:** native `wrk` 4.2.0 on the load client, with `benchmarks/lab/scenarios/load/benign-mix.lua`  
**Runner:** `benchmarks/lab/runners/run-load.sh` (on the lab server)

Two runs against Albedo (`ftw.local`), both from the load client over the VPN:

1. **Through HAProxy+Coraza** — `http://LAB_SERVER_ADDR:HAPROXY_HTTP_PORT/` (production WAF path)
2. **Direct to Albedo** — `http://LAB_SERVER_ADDR:18080/`, the baseline-only port, published only on `LAB_SERVER_ADDR`

Overhead = WAF_value − direct_value.  
Config: 2 threads, 20 connections, 30-second duration (`LOAD_THREADS`, `LOAD_CONNECTIONS`, `LOAD_DURATION`). The mix has 10 requests: 8 GETs (pages, assets, search, API) and 2 POSTs (a form login and a JSON body), because Coraza also inspects request bodies. Every request carries `Host: ftw.local` and the correlation headers. Albedo answers 200 to all of them, so any non-2xx response through the WAF is a false positive; a run with errors on either path is marked `valid: false` in `performance.json`, because fast 403s would inflate RPS.

During the WAF run the server samples the `coraza` and `haproxy` containers with `docker stats` (target interval 2 s, `RESOURCE_SAMPLE_INTERVAL_S`). Each `docker stats` call takes about a second itself, so the files record the achieved mean interval (`interval_s_mean`) and the number of samples next to the target interval.

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
| p50/p95/p99 latency | 50th/95th/99th percentile of request round-trip time (ms), from wrk's Lua `latency:percentile()` |
| Latency overhead    | Latency(WAF) − Latency(direct) per percentile                                          |
| RPS                 | Requests per second at sustained load                                                  |
| RPS degradation %   | (RPS_direct − RPS_WAF) / RPS_direct × 100                                              |
| Memory peak (MB)    | Highest `docker stats` memory sample of the container during the WAF run              |
| CPU avg %           | Mean of the `docker stats` CPU samples (100 % = one core) during the WAF run           |

### Results schema

Each scenario writes `benchmarks/results/run-<RUN_ID>-<POLICY>/<scenario>/summary.json`. Aggregated output: `benchmarks/results/run-<RUN_ID>-<POLICY>/results.csv` (one row per scenario).

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

On the lab server:

```bash
git clone https://github.com/bihius/guard-proxy.git ~/guard-proxy
cd ~/guard-proxy
git submodule update --init --recursive   # CRS v4.25.0

cp docker/.env.example docker/.env
cp benchmarks/lab/.env.example benchmarks/lab/.env
# docker/.env must include ADMIN_EMAIL and ADMIN_PASSWORD for lab seeding.
# Do not set LAB_POLICY_* or LAB_PL2_POLICY_* in benchmarks/lab/.env.
```

On the load client: install `wrk` (`brew install wrk`) and clone the repository at the same commit as the server; the printed command uses `benchmarks/lab/scenarios/load/benign-mix.lua` relative to the repository root. The command uses `env VAR=value wrk …`, which works in bash, zsh and fish.

### 8.2 The evaluation (one command)

On the lab server, set `LAB_SERVER_ADDR=10.99.99.20` in `benchmarks/lab/.env`, then:

```bash
make -C benchmarks lab-up
make -C benchmarks eval-sweep RUN_ID=<id> LOAD_CLIENT=manual
```

All lab targets live in `benchmarks/Makefile`; run them with `make -C benchmarks …` from the repository root (or plain `make …` inside `benchmarks/`).

`eval-sweep` stops at the first failing step. It:

1. writes the **PL1** profile into both lab policies and applies the config;
2. runs Test 1 (corpus on `wp.local`), Test 2 (go-ftw on `ftw.local`) and Test 3 (wrk from the load client to `ftw.local`), then aggregates `results.csv` into `benchmarks/results/run-<id>-pl1/`. Test 3 pauses twice, once for the WAF run and once for the direct run. Each time, run the printed command on the client, press Enter on the server as you start it (resource sampling starts then), and paste wrk's whole output when it finishes; reading stops at the `WRK_SUMMARY` line;
3. writes the **PL2** profile and repeats all three tests into `benchmarks/results/run-<id>-pl2/`;
4. prints both result tables.

Every runner reads the policy that protects its target vhost back from the API and records it in `summary.json` (paranoia, thresholds, mode, rate limiting, GeoIP mode and the number of exclusions, overrides and custom rules); it warns when those settings do not match the `POLICY` profile. `manifest.json` records the git SHA of the checkout, so commit lab changes before a measured run.

Without `LOAD_CLIENT=manual`, `make -C benchmarks eval-sweep RUN_ID=<id>` runs everything on one machine (wrk in a container) without pauses; use that for smoke runs, not for thesis numbers.

After the evaluation, set `LAB_SERVER_ADDR` back to `127.0.0.1` and run `make -C benchmarks lab-up` again if the direct port should no longer be reachable over the VPN.

### 8.3 Manual runs

```bash
make -C benchmarks set-policy POLICY=pl2                     # both lab vhosts
make -C benchmarks eval-corpus RUN_ID=<id> POLICY=pl2        # one test
make -C benchmarks eval-load RUN_ID=<id> POLICY=pl2 LOAD_CLIENT=manual
make -C benchmarks results RUN_ID=<id> POLICY=pl2
```

`RUN_ID` is the base ID; the Makefile appends `-pl1` or `-pl2`.

---

## 9. Threats to Validity

### 9.1 Shared lab server

The lab server also runs unrelated services. They can compete for CPU, memory and I/O with the WAF stack and the targets. **Mitigation:** `manifest.json` records the load average at the start of each run; run sweeps when the other services are idle, repeat the measurement, and report the variance. `LAB_WAF_CPUSET` can pin the lab containers when the server has spare cores.

### 9.2 Load generator over a VPN

`wrk` runs on a separate client, so it does not take CPU from the WAF. Its traffic crosses the WireGuard VPN, which adds latency and jitter to every request. Both the WAF path and the direct path take the same route, so the overhead (WAF − direct) remains comparable, but absolute latencies include the VPN and are not comparable with a LAN or loopback measurement. Resource sampling starts when the operator presses Enter, so its window can be offset from the wrk run by a second or two. Do not run other load on either host during a measurement.

### 9.3 WordPress false positives without CRS exclusions

WordPress is tested without CRS application exclusion plugins (not yet implemented in the backend). Any false positives are for an **untuned** WAF+CMS combination under a documented policy. They are not generalized to all Guard Proxy deployments.

### 9.4 Small corpus

The tagged corpus has 39 benign requests and 100 attack requests. TPR and FPR describe this corpus, not attack traffic in general; one benign case changes the FPR by about 2.6 percentage points.

### 9.5 Lab-specific go-ftw deviations

The lab overrides every CRS test's `Host` header to route it to `ftw.local`, and HAProxy parses and normalizes requests before Coraza sees them. Tests that depend on their own `Host` header or on malformed HTTP that HAProxy rejects or rewrites fail for that reason, not because of a CRS rule. The thesis groups failed test IDs by cause.

### 9.6 Resource sampling resolution

`docker stats` gives a handful of samples per 30-second run (see `samples` and `interval_s_mean`). CPU and memory figures are therefore coarse averages and peaks, not continuous measurements.

---

## 10. Results Format

### summary.json (per scenario)

```json
{
  "run_id": "20261010-pl1",
  "scenario": "corpus-<vhost> | ftw | load-<vhost>",
  "target_vhost": "ftw.local",
  "policy": {
    "name": "Lab ftw.local",
    "paranoia": 1,
    "inbound_threshold": 5,
    "outbound_threshold": 4,
    "mode": "block",
    "rate_limiting": false,
    "geoip_mode": "off",
    "rule_exclusions": 0,
    "rule_overrides": 0,
    "custom_rules": 0
  },
  "detection": {},
  "performance": {
    "rps": 4120.5,
    "baseline_rps": 5980.0,
    "rps_degradation_pct": 31.1,
    "latency_ms": { "p50": 2.1, "p95": 7.8, "p99": 18.4 },
    "baseline_latency_ms": { "p50": 1.2, "p95": 4.7, "p99": 11.4 },
    "latency_overhead_ms": { "p50": 0.9, "p95": 3.1, "p99": 7.0 },
    "waf_errors": 0,
    "baseline_errors": 0,
    "valid": true,
    "config": {
      "threads": 2, "connections": 20, "duration": "30s",
      "mode": "manual", "wrk_image": null, "wrk_version": null,
      "waf_url": "http://10.99.99.20:8081/", "direct_url": "http://10.99.99.20:18080/"
    }
  },
  "resources": {
    "coraza": { "mem_mb_peak": 410.2, "cpu_pct_avg": 62.0, "samples": 12, "interval_s_target": 2.0, "interval_s_mean": 2.51, "window_s": 27.6 },
    "haproxy": { "mem_mb_peak": 95.1, "cpu_pct_avg": 40.0, "samples": 12, "interval_s_target": 2.0, "interval_s_mean": 2.49, "window_s": 27.4 }
  }
}
```

The corpus `detection` block holds `true_positive`, `false_negative`, `true_negative`, `false_positive`, `tpr`, `fpr`, `total_cases`, `blocked_cases` and the outcome of every case; the go-ftw block holds `crs_conformance_rate`, `crs_run`, `crs_passed`, `crs_failed`, `crs_excluded` and the split by test expectation.

### results.csv

Flat CSV with one row per scenario run. Consumed directly by `thesis/chapters/06-testy.md` tables.

Columns include: `run_id`, `scenario`, `target_vhost`, `policy`, `paranoia_level`, `tpr`, `fpr`, `crs_conformance_rate`, `crs_run`, `crs_passed`, `crs_failed`, `crs_excluded`, `tp`, `fn`, `tn`, `fp`, `corpus_cases`, `waf_blocks_from_log`, `rps_waf`, `rps_direct`, `rps_degradation_pct`, WAF/direct/overhead latency percentiles, `load_valid`, and resource fields.

`policy` is the name of the target vhost's own policy (`Lab <domain>`) and `paranoia_level` its paranoia level at run time: `1` under the `pl1` profile and `2` under `pl2`.
