"""Shared evaluation metrics helpers for benchmark runner scripts.

The functions in this module are intentionally dependency-free so they can run
on the lab host without installing the backend Python environment.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BLOCK_STATUS = 403
EVAL_HEADER_RUN = "x-gp-eval-run"
EVAL_HEADER_SCENARIO = "x-gp-eval-scenario"
EVAL_HEADER_CASE = "x-gp-eval-case"


def load_json_lines(path: str | Path) -> list[dict[str, Any]]:
    """Load newline-delimited JSON audit events, ignoring malformed lines."""

    events: list[dict[str, Any]] = []
    p = Path(path)
    if not p.exists():
        return events
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def request_headers(event: dict[str, Any]) -> dict[str, str]:
    """Return lower-cased request headers from a Coraza audit event."""

    txn = _as_dict(event.get("transaction"))
    request = _as_dict(txn.get("request"))
    raw_headers = _as_dict(request.get("headers"))
    headers: dict[str, str] = {}
    for key, raw_value in raw_headers.items():
        if not isinstance(key, str):
            continue
        value = raw_value[0] if isinstance(raw_value, list) and raw_value else raw_value
        if isinstance(value, str):
            headers[key.lower()] = value
    return headers


def eval_tags(event: dict[str, Any]) -> dict[str, str]:
    """Extract benchmark correlation headers from an audit event."""

    headers = request_headers(event)
    tags: dict[str, str] = {}
    for name in (EVAL_HEADER_RUN, EVAL_HEADER_SCENARIO, EVAL_HEADER_CASE):
        value = headers.get(name)
        if value:
            tags[name] = value
    return tags


def is_blocked_event(event: dict[str, Any]) -> bool:
    """Return whether a Coraza event represents an interrupted/blocking decision."""

    txn = _as_dict(event.get("transaction"))
    response = _as_dict(txn.get("response"))
    status = _coerce_int(response.get("status"))
    return bool(txn.get("is_interrupted")) or status == BLOCK_STATUS


def count_blocks(events: list[dict[str, Any]], run_id: str) -> dict[str, int]:
    """Count blocked audit events of one run, by eval scenario.

    The Coraza audit log is cumulative across runs, so events are matched on
    the ``X-GP-Eval-Run`` tag; untagged and other runs' events are ignored.
    """

    by_scenario: dict[str, int] = {}
    seen: set[str] = set()
    for event in events:
        event_id = _event_identity(event)
        if event_id in seen:
            continue
        seen.add(event_id)
        tags = eval_tags(event)
        if tags.get(EVAL_HEADER_RUN) != run_id or not is_blocked_event(event):
            continue
        scenario = tags.get(EVAL_HEADER_SCENARIO, "untagged")
        by_scenario[scenario] = by_scenario.get(scenario, 0) + 1
    return by_scenario


def summarize_tagged_corpus(
    cases: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    run_id: str,
    scenario: str,
) -> dict[str, Any]:
    """Compute TP/FN/TN/FP for a labeled, tagged benchmark corpus.

    Coraza runs with ``SecAuditEngine RelevantOnly``. Correctly allowed benign
    requests often produce no audit event, so absence of a tagged blocking event
    is treated as an allowed outcome.
    """

    blocked_cases: set[str] = set()
    matched_cases: set[str] = set()
    seen: set[str] = set()
    for event in events:
        event_id = _event_identity(event)
        if event_id in seen:
            continue
        seen.add(event_id)
        tags = eval_tags(event)
        if tags.get(EVAL_HEADER_RUN) != run_id:
            continue
        if tags.get(EVAL_HEADER_SCENARIO) != scenario:
            continue
        case_id = tags.get(EVAL_HEADER_CASE)
        if not case_id:
            continue
        matched_cases.add(case_id)
        if is_blocked_event(event):
            blocked_cases.add(case_id)

    tp = fn = tn = fp = 0
    case_results: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["case_id"])
        expected = str(case["expected"])
        blocked = case_id in blocked_cases
        if expected == "block" and blocked:
            outcome = "tp"
            tp += 1
        elif expected == "block":
            outcome = "fn"
            fn += 1
        elif expected == "allow" and blocked:
            outcome = "fp"
            fp += 1
        else:
            outcome = "tn"
            tn += 1
        case_results.append(
            {
                **case,
                "audit_event_seen": case_id in matched_cases,
                "blocked": blocked,
                "outcome": outcome,
            }
        )

    tpr = tp / (tp + fn) if (tp + fn) else None
    fpr = fp / (fp + tn) if (fp + tn) else None
    return {
        "true_positive": tp,
        "false_negative": fn,
        "true_negative": tn,
        "false_positive": fp,
        "tpr": round(tpr, 4) if tpr is not None else None,
        "fpr": round(fpr, 4) if fpr is not None else None,
        "total_cases": len(cases),
        "blocked_cases": len(blocked_cases),
        "note": (
            "Computed only for this labeled tagged corpus. Absence of a matching "
            "RelevantOnly audit event is treated as allow."
        ),
        "cases": case_results,
    }


def parse_go_ftw_result(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize go-ftw ``-o json`` output into passed/failed/ignored ID lists."""

    passed = _string_list(raw.get("success"))
    failed = _string_list(raw.get("failed"))
    ignored = _string_list(raw.get("ignored"))
    return {"passed_ids": passed, "failed_ids": failed, "ignored_ids": ignored}


def crs_rule_paranoia_levels(rules_dir: str | Path) -> dict[str, int]:
    """Map every CRS rule ID to the paranoia level at which it is active.

    Each rule carries a ``paranoia-level/N`` tag. Rules without one inherit the
    level of the ``TX:DETECTION_PARANOIA_LEVEL "@lt N"`` gate above them in
    their file (the gate skips everything below it until PL N is enabled).
    """

    levels: dict[str, int] = {}
    for path in sorted(Path(rules_dir).glob("*.conf")):
        gate_level = 1
        for block in _directive_blocks(path):
            gate = re.search(r'DETECTION_PARANOIA_LEVEL\s+"@lt\s+(\d)"', block)
            if gate:
                gate_level = int(gate.group(1))
                continue
            rule_id = re.search(r"\bid:(\d+)", block)
            if not rule_id:
                continue
            tag = re.search(r"paranoia-level/(\d)", block)
            levels[rule_id.group(1)] = int(tag.group(1)) if tag else gate_level
    return levels


def classify_ftw_tests(tests_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Read every CRS regression test and record what it expects.

    ``expected`` is ``"match"`` when the test expects its rule to fire
    (``expect_ids``/``log_contains``, or a 403 status), ``"no_match"`` when
    it expects the rule to stay silent (``no_expect_ids``/``no_log_contains``),
    and ``"other"`` when it only asserts another HTTP status (typically a 400
    from the web server for a malformed request).
    ``phase`` is ``"request"`` or ``"response"`` from the rule file directory.
    """

    classifications: dict[str, dict[str, Any]] = {}
    base = Path(tests_dir)
    for path in sorted(base.rglob("*.y*ml")):
        phase = "response" if path.parent.name.startswith("RESPONSE-") else "request"
        for test_id, expected in _classify_ftw_yaml(path).items():
            classifications[test_id] = {
                "rule_id": path.stem,
                "expected": expected,
                "phase": phase,
            }
    return classifications


def ftw_exclusions(
    classifications: dict[str, dict[str, Any]],
    rule_levels: dict[str, int],
    paranoia: int,
) -> dict[str, str]:
    """Return go-ftw ``ignore`` entries (test-ID regex -> reason).

    Two kinds of tests cannot pass in this setup by design, so they are left
    out instead of counted as failures:

    - rules above the policy's paranoia level are not loaded at all;
    - response rules never run, because the SPOA only inspects requests
      (``response_check: false`` in the generated coraza-spoa.yaml).
    """

    reasons: dict[str, str] = {}
    for info in classifications.values():
        rule_id = info["rule_id"]
        if info["phase"] == "response":
            reasons[rule_id] = "response rule: Guard Proxy inspects requests only"
        elif rule_levels.get(rule_id, 1) > paranoia:
            reasons[rule_id] = (
                f"rule active from PL{rule_levels[rule_id]}, policy runs PL{paranoia}"
            )
    return {f"^{rule_id}-": reason for rule_id, reason in sorted(reasons.items())}


def summarize_ftw(
    raw: dict[str, Any],
    classifications: dict[str, dict[str, Any]],
    exclusions: dict[str, str],
) -> dict[str, Any]:
    """Summarize a log-mode go-ftw run: pass rate split by test expectation."""

    result = parse_go_ftw_result(raw)
    passed_ids = result["passed_ids"]
    failed_ids = result["failed_ids"]
    run = len(passed_ids) + len(failed_ids)

    by_expected: dict[str, dict[str, int]] = {
        "match": {"passed": 0, "failed": 0},
        "no_match": {"passed": 0, "failed": 0},
        "other": {"passed": 0, "failed": 0},
    }
    for outcome, ids in (("passed", passed_ids), ("failed", failed_ids)):
        for test_id in ids:
            expected = classifications.get(test_id, {}).get("expected", "other")
            by_expected[expected][outcome] += 1

    excluded_by_reason: dict[str, int] = {}
    for test_id in result["ignored_ids"]:
        reason = _exclusion_reason(test_id, exclusions)
        excluded_by_reason[reason] = excluded_by_reason.get(reason, 0) + 1

    conformance = len(passed_ids) / run if run else None
    return {
        "crs_conformance_rate": round(conformance, 4) if conformance is not None else None,
        "crs_run": run,
        "crs_passed": len(passed_ids),
        "crs_failed": len(failed_ids),
        "crs_excluded": len(result["ignored_ids"]),
        "excluded_by_reason": dict(sorted(excluded_by_reason.items())),
        "expect_match_passed": by_expected["match"]["passed"],
        "expect_match_failed": by_expected["match"]["failed"],
        "expect_no_match_passed": by_expected["no_match"]["passed"],
        "expect_no_match_failed": by_expected["no_match"]["failed"],
        "expect_other_passed": by_expected["other"]["passed"],
        "expect_other_failed": by_expected["other"]["failed"],
        "failed_ids": failed_ids,
        "note": (
            "go-ftw in log mode: a test passes when the rule IDs it expects fire "
            "(or stay silent) in the Coraza log, plus any status it asserts. "
            "No TPR/FPR is estimated."
        ),
    }


def _exclusion_reason(test_id: str, exclusions: dict[str, str]) -> str:
    for pattern, reason in exclusions.items():
        if re.match(pattern, test_id):
            return "response rule" if reason.startswith("response") else "above paranoia level"
    return "unlisted"


def _directive_blocks(path: Path) -> list[str]:
    """Split a SecLang file into directives, joining backslash continuations."""

    blocks: list[str] = []
    current: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not current and (not stripped or stripped.startswith("#")):
            continue
        current.append(stripped.rstrip("\\"))
        if not stripped.endswith("\\"):
            blocks.append(" ".join(current))
            current = []
    if current:
        blocks.append(" ".join(current))
    return blocks


def _classify_ftw_yaml(path: Path) -> dict[str, str]:
    rule_id = path.stem
    expectations: dict[str, set[str]] = {}
    current_id: str | None = None

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = raw_line.strip()
        test_id_match = re.match(r"-?\s*test_id:\s*['\"]?(\w+)", stripped)
        if test_id_match:
            current_id = f"{rule_id}-{test_id_match.group(1)}"
            expectations.setdefault(current_id, set())
            continue
        if current_id is None:
            continue
        key = re.match(r"(no_expect_ids|expect_ids|no_log_contains|log_contains|status):\s*(.*)", stripped)
        if not key:
            continue
        name, value = key.group(1), key.group(2).strip()
        if name == "status":
            if value.strip("'\"").startswith(str(BLOCK_STATUS)):
                expectations[current_id].add("match")
        elif value in ("[]", "''", '""'):
            continue
        elif name.startswith("no_"):
            expectations[current_id].add("no_match")
        else:
            expectations[current_id].add("match")

    return {
        test_id: "match" if "match" in found else "no_match" if "no_match" in found else "other"
        for test_id, found in expectations.items()
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _event_identity(event: dict[str, Any]) -> str:
    txn = _as_dict(event.get("transaction"))
    event_id = txn.get("id")
    if isinstance(event_id, str) and event_id:
        return event_id
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
