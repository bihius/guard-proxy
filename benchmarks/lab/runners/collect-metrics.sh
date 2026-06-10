#!/usr/bin/env bash
# collect-metrics.sh — Aggregate all scenario summaries into results.csv.
#
# Reads all summary.json files in a run directory and produces:
#   benchmarks/results/run-<RUN_ID>/results.csv   — flat table for thesis tables
#   benchmarks/results/run-<RUN_ID>/report.json   — full structured report
#
# Cross-references tagged Coraza audit snapshots for block counts. TP/FP counts
# are only computed by runners that own a labeled tagged corpus.
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
PYTHONPATH="${SCRIPT_DIR}" python3 - <<PY
import json, os, glob, csv, sys

from eval_metrics import count_blocks, load_json_lines

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
audit_paths = sorted(glob.glob(os.path.join(run_dir, "*/coraza-audit.log")))
if audit_log and os.path.exists(audit_log):
    audit_paths.append(audit_log)

audit_events = []
seen_paths = set()
for path in audit_paths:
    if path in seen_paths:
        continue
    seen_paths.add(path)
    audit_events.extend(load_json_lines(path))

block_counts = count_blocks(audit_events)
blocked_by_vhost = block_counts["by_vhost"]
blocked_by_scenario = block_counts["by_scenario"]
if audit_events:
    print(f"Audit log: found blocks per scenario: {blocked_by_scenario}")
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
    scenario = s.get("scenario", "")
    blocked = blocked_by_scenario.get(scenario, blocked_by_vhost.get(vhost, ""))

    row = {
        "run_id":             run_id,
        "scenario":           scenario,
        "target_vhost":       vhost,
        "policy":             s.get("policy", {}).get("name", ""),
        "paranoia_level":     s.get("policy", {}).get("paranoia", ""),
        "tpr":                det.get("tpr", ""),
        "fpr":                det.get("fpr", ""),
        "crs_conformance_rate": det.get("crs_conformance_rate", ""),
        "crs_passed":         det.get("crs_passed", ""),
        "crs_failed":         det.get("crs_failed", ""),
        "expected_block_tests": det.get("expected_block_tests", ""),
        "expected_allow_tests": det.get("expected_allow_tests", ""),
        "tp":                 det.get("true_positive", ""),
        "fn":                 det.get("false_negative", ""),
        "tn":                 det.get("true_negative", ""),
        "fp":                 det.get("false_positive", ""),
        "corpus_cases":       det.get("total_cases", ""),
        "zap_total_alerts":    det.get("total_alerts", ""),
        "zap_attack_alerts":   det.get("attack_severity_alerts", ""),
        "nuclei_findings":    det.get("total_findings", ""),
        "nuclei_waf_relevant_findings": det.get("waf_relevant_findings", ""),
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
print(f"{'SCENARIO':<35} {'CRS%':>6} {'TPR':>6} {'FPR':>6} {'RPS':>8} {'DEG%':>6} {'p99ms':>7}")
print("-" * 70)
for row in csv_rows:
    crs = f"{float(row['crs_conformance_rate'])*100:.1f}%" if row['crs_conformance_rate'] != '' else "—"
    tpr = f"{float(row['tpr'])*100:.1f}%" if row['tpr'] != '' else "—"
    fpr = f"{float(row['fpr'])*100:.1f}%" if row['fpr'] != '' else "—"
    rps = f"{float(row['rps_waf']):.0f}"  if row['rps_waf'] != '' else "—"
    deg = f"{row['rps_degradation_pct']}%" if row['rps_degradation_pct'] != '' else "—"
    p99 = f"{row['lat_p99_ms']}"           if row['lat_p99_ms'] != '' else "—"
    print(f"{row['scenario']:<35} {crs:>6} {tpr:>6} {fpr:>6} {rps:>8} {deg:>6} {p99:>7}")
PY

echo ""
echo "Done. Results → ${RUN_DIR}/"
echo ""
echo "To copy to thesis assets (after review):"
echo "  cp ${RUN_DIR}/results.csv thesis/assets/figures/eval-results-${RUN_ID}.csv"
