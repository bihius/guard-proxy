#!/usr/bin/env bash
# run-nuclei.sh — CVE / exposure template scan via Nuclei.
#
# Fires Nuclei's curated attack templates (sqli, xss, lfi, etc.) against the
# lab targets through HAProxy+Coraza. Nuclei is supplemental reached-app/bypass
# evidence, not a clean TPR source.
#
# Output:
#   benchmarks/results/run-<RUN_ID>/nuclei-<vhost>/raw.jsonl
#   benchmarks/results/run-<RUN_ID>/nuclei-<vhost>/summary.json
#
# Usage:
#   RUN_ID=... bash benchmarks/lab/runners/run-nuclei.sh
#   RUN_ID=... TARGET_VHOST=juice.local bash benchmarks/lab/runners/run-nuclei.sh

set -Eeuo pipefail
: "${RUN_ID:=$(date +%Y%m%d-%H%M%S)}"
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TARGET_VHOST="${TARGET_VHOST:-${LAB_JUICESHOP_DOMAIN}}"
NUCLEI_IMAGE="projectdiscovery/nuclei:v3.3.9"
NUCLEI_CONF="${REPO_ROOT}/benchmarks/lab/scenarios/nuclei/nuclei.yaml"

# HAProxy on port 80 inside gp_internal, Host: header injected per-request.
TARGET_URL="http://haproxy:80"

write_manifest
SCENARIO="nuclei-${TARGET_VHOST}"
OUT_DIR="$(setup_run_dir "${SCENARIO}")"
export OUT_DIR TARGET_VHOST   # must be set before the Python heredoc reads os.environ

echo "=== Nuclei CVE template scan ==="
echo "Target vhost : ${TARGET_VHOST} → ${TARGET_URL}"
echo "Output dir   : ${OUT_DIR}"
echo "Image        : ${NUCLEI_IMAGE}"
echo ""

# Pull nuclei-templates inside the container on first run. Header flags inject
# the vhost and benchmark correlation tags.
docker run --rm --cpuset-cpus="21-23" \
  --network "${DOCKER_NETWORK}" \
  -v "${OUT_DIR}:/output:rw" \
  -v "${NUCLEI_CONF}:/nuclei.yaml:ro" \
  "${NUCLEI_IMAGE}" \
  -config /nuclei.yaml \
  -u "${TARGET_URL}" \
  -header "Host: ${TARGET_VHOST}" \
  -header "X-GP-Eval-Run: ${RUN_ID}" \
  -header "X-GP-Eval-Scenario: ${SCENARIO}" \
  -header "X-GP-Eval-Case: nuclei" \
  -jsonl -output /output/raw.jsonl \
  -update-templates \
  2>/dev/null || true

echo "Nuclei scan complete. Parsing results..."
copy_audit_log_snapshot "${OUT_DIR}"

python3 - <<'PY'
import json, os

out_dir  = os.environ.get("OUT_DIR", ".")
raw_file = os.path.join(out_dir, "raw.jsonl")
vhost    = os.environ.get("TARGET_VHOST", "unknown")

findings = []
if os.path.exists(raw_file):
    with open(raw_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    findings.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

# Severity classification for supplemental scanner reporting. A medium/high/
# critical finding means a template matched the application response and is
# reached-app evidence. It is not a TPR denominator.

WAF_RELEVANT = {"critical", "high", "medium"}
fn_findings = [f for f in findings if f.get("info", {}).get("severity", "").lower() in WAF_RELEVANT]
info_findings = [f for f in findings if f.get("info", {}).get("severity", "").lower() not in WAF_RELEVANT]

detection = {
    "total_findings": len(findings),
    "waf_relevant_findings": len(fn_findings),
    "info_findings": len(info_findings),
    "note": "Supplemental scanner evidence only. Medium/high/critical findings are reached-app findings, not a complete TPR/FN measurement.",
    "top_findings": [
        {
            "template_id": f.get("template-id"),
            "severity": f.get("info", {}).get("severity"),
            "name": f.get("info", {}).get("name"),
            "matched_at": f.get("matched-at")
        }
        for f in sorted(fn_findings, key=lambda x: {"critical":0,"high":1,"medium":2}.get(x.get("info",{}).get("severity",""),3))[:20]
    ]
}

print(json.dumps(detection, indent=2))

with open(os.path.join(out_dir, "detection.json"), "w") as f:
    json.dump(detection, f, indent=2)
PY

DETECTION="$(cat "${OUT_DIR}/detection.json")"
resolve_policy

write_summary "${SCENARIO}" "${TARGET_VHOST}" "${POLICY_NAME}" "${DETECTION}" "{}" "{}" "${POLICY_PARANOIA}"

echo ""
echo "Nuclei findings (waf-relevant): $(python3 -c "import json; d=json.load(open('${OUT_DIR}/detection.json')); print(d.get('waf_relevant_findings', 'n/a'))")"
echo "Results → ${OUT_DIR}/"
