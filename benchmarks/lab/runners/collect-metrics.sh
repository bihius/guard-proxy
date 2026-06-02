#!/usr/bin/env bash
# collect-metrics.sh — Aggregate all scenario summaries into results.csv.
#
# Reads all summary.json files in a run directory and produces:
#   benchmarks/results/run-<RUN_ID>/results.csv   — flat table for thesis tables
#   benchmarks/results/run-<RUN_ID>/report.json   — full structured report
#
# Optionally cross-references the Coraza audit log to compute confirmed
# TP/FP counts for ZAP and Nuclei scenarios.
#
# Usage:
#   RUN_ID=20260602-141500 bash benchmarks/lab/runners/collect-metrics.sh
#   RUN_ID=... AUDIT_LOG=/path/to/audit.log bash benchmarks/lab/runners/collect-metrics.sh

set -Eeuo pipefail
: "${RUN_ID:=$(date +%Y%m%d-%H%M%S)}"
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

RUN_DIR="${REPO_ROOT}/benchmarks/results/run-${RUN_ID}"
# Coraza audit log — mounted from the coraza_audit Docker volume.
# If not provided, skip audit-log cross-reference.
AUDIT_LOG="${AUDIT_LOG:-}"

if [[ ! -d "${RUN_DIR}" ]]; then
  echo "Run directory not found: ${RUN_DIR}" >&2
  echo "Set RUN_ID to an existing run." >&2
  exit 1
fi

echo "=== Aggregating metrics for run ${RUN_ID} ==="

# ── Optional: extract audit log from Docker volume ─────────────────────────
if [[ -z "${AUDIT_LOG}" ]]; then
  AUDIT_LOG="${RUN_DIR}/coraza-audit.log"
  if ! docker cp "$(docker ps --filter "name=coraza" --format "{{.ID}}" | head -1)":/var/log/coraza/audit.log \
       "${AUDIT_LOG}" 2>/dev/null; then
    echo "Note: could not copy audit log from coraza container. Skipping log cross-reference."
    AUDIT_LOG=""
  fi
fi

# ── Aggregate summaries ────────────────────────────────────────────────────
python3 - <<PY
import json, os, glob, csv, sys

run_dir    = "${RUN_DIR}"
audit_log  = "${AUDIT_LOG}"
run_id     = "${RUN_ID}"

# Collect all summary.json files.
summaries = []
for path in sorted(glob.glob(os.path.join(run_dir, "*/summary.json"))):
    with open(path) as f:
        try:
            summaries.append(json.load(f))
        except json.JSONDecodeError as e:
            print(f"Warning: could not parse {path}: {e}", file=sys.stderr)

if not summaries:
    print("No summary.json files found in run directory.", file=sys.stderr)
    sys.exit(1)

# ── Audit log cross-reference ──────────────────────────────────────────────
# Parse Coraza JSON audit log to count total blocked requests per vhost
# and identify transactions by WAF rule matches.
blocked_by_vhost = {}
if audit_log and os.path.exists(audit_log):
    with open(audit_log) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                # Coraza audit log JSON schema: top-level keys vary by config.
                # Standard keys: transaction.host_name, transaction.response.status
                txn = entry.get("transaction", {})
                vhost = txn.get("host_name", "unknown")
                response = txn.get("response", {})
                status = response.get("status", 200)
                if status == 403:
                    blocked_by_vhost[vhost] = blocked_by_vhost.get(vhost, 0) + 1
            except (json.JSONDecodeError, AttributeError):
                pass
    print(f"Audit log: found blocks per vhost: {blocked_by_vhost}")

# ── Write aggregated CSV ───────────────────────────────────────────────────
csv_path = os.path.join(run_dir, "results.csv")
report_path = os.path.join(run_dir, "report.json")

csv_rows = []
for s in summaries:
    det  = s.get("detection", {})
    perf = s.get("performance", {})
    lat  = perf.get("latency_ms", {})
    lat_oh = perf.get("latency_overhead_ms", {})
    res  = s.get("resources", {})
    cor  = res.get("coraza", {})
    hap  = res.get("haproxy", {})

    vhost = s.get("target_vhost", "")
    blocked = blocked_by_vhost.get(vhost, "")

    row = {
        "run_id":             run_id,
        "scenario":           s.get("scenario", ""),
        "target_vhost":       vhost,
        "policy":             s.get("policy", {}).get("name", ""),
        "tpr":                det.get("tpr", ""),
        "fpr":                det.get("fpr", ""),
        "tp":                 det.get("true_positive", ""),
        "fn":                 det.get("false_negative", ""),
        "tn":                 det.get("true_negative", ""),
        "fp":                 det.get("false_positive", ""),
        "waf_blocks_from_log":  blocked,
        "rps_waf":            perf.get("rps", ""),
        "rps_direct":         perf.get("baseline_rps", ""),
        "rps_degradation_pct": perf.get("rps_degradation_pct", ""),
        "lat_p50_ms":         lat.get("p50", ""),
        "lat_p95_ms":         lat.get("p95", ""),
        "lat_p99_ms":         lat.get("p99", ""),
        "lat_oh_p50_ms":      lat_oh.get("p50", ""),
        "lat_oh_p95_ms":      lat_oh.get("p95", ""),
        "lat_oh_p99_ms":      lat_oh.get("p99", ""),
        "coraza_mem_mb_peak": cor.get("mem_mb_peak", ""),
        "coraza_cpu_pct_avg": cor.get("cpu_pct_avg", ""),
        "haproxy_mem_mb_peak": hap.get("mem_mb_peak", ""),
        "haproxy_cpu_pct_avg": hap.get("cpu_pct_avg", ""),
    }
    csv_rows.append(row)

if csv_rows:
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"CSV written to {csv_path}")

# Full JSON report.
report = {
    "run_id": run_id,
    "scenarios": len(summaries),
    "summaries": summaries,
    "audit_log_blocks": blocked_by_vhost,
}
with open(report_path, "w") as f:
    json.dump(report, f, indent=2)
print(f"Report written to {report_path}")

# Print a quick summary table.
print()
print(f"{'SCENARIO':<35} {'TPR':>6} {'FPR':>6} {'RPS':>8} {'DEG%':>6} {'p99ms':>7}")
print("-" * 70)
for row in csv_rows:
    tpr = f"{float(row['tpr'])*100:.1f}%" if row['tpr'] != '' else "—"
    fpr = f"{float(row['fpr'])*100:.1f}%" if row['fpr'] != '' else "—"
    rps = f"{float(row['rps_waf']):.0f}"  if row['rps_waf'] != '' else "—"
    deg = f"{row['rps_degradation_pct']}%" if row['rps_degradation_pct'] != '' else "—"
    p99 = f"{row['lat_p99_ms']}"           if row['lat_p99_ms'] != '' else "—"
    print(f"{row['scenario']:<35} {tpr:>6} {fpr:>6} {rps:>8} {deg:>6} {p99:>7}")
PY

echo ""
echo "Done. Results → ${RUN_DIR}/"
echo ""
echo "To copy to thesis assets (after review):"
echo "  cp ${RUN_DIR}/results.csv thesis/assets/figures/eval-results-${RUN_ID}.csv"
