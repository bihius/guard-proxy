"""Shared evaluation metrics helpers for benchmark runner scripts.

The functions in this module are intentionally dependency-free so they can run
inside the lab LXC without installing the backend Python environment.
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


def count_blocks(events: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Count blocked audit events by vhost and eval scenario."""

    by_vhost: dict[str, int] = {}
    by_scenario: dict[str, int] = {}
    seen: set[str] = set()
    for event in events:
        event_id = _event_identity(event)
        if event_id in seen:
            continue
        seen.add(event_id)
        if not is_blocked_event(event):
            continue
        txn = _as_dict(event.get("transaction"))
        request = _as_dict(txn.get("request"))
        headers = request_headers(event)
        vhost = headers.get("host", "unknown").split(":", 1)[0].lower()
        by_vhost[vhost] = by_vhost.get(vhost, 0) + 1
        scenario = headers.get(EVAL_HEADER_SCENARIO)
        if scenario:
            by_scenario[scenario] = by_scenario.get(scenario, 0) + 1
        elif request.get("uri"):
            by_scenario.setdefault("untagged", 0)
    return {"by_vhost": by_vhost, "by_scenario": by_scenario}


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
    """Normalize supported go-ftw JSON output shapes."""

    if "success" in raw or "failed" in raw:
        success = _string_list(raw.get("success"))
        failed = _string_list(raw.get("failed"))
        skipped = _string_list(raw.get("skipped"))
        return {
            "passed_ids": success,
            "failed_ids": failed,
            "skipped_ids": skipped,
            "run": _coerce_int(raw.get("run")) or len(success) + len(failed),
            "passed": len(success),
            "failed": len(failed),
            "skipped": len(skipped),
        }

    passed = _coerce_int(raw.get("pass")) or 0
    failed_count = _coerce_int(raw.get("fail")) or 0
    skipped = _coerce_int(raw.get("skip")) or 0
    return {
        "passed_ids": [],
        "failed_ids": [],
        "skipped_ids": [],
        "run": passed + failed_count,
        "passed": passed,
        "failed": failed_count,
        "skipped": skipped,
    }


def classify_ftw_tests(root: str | Path) -> dict[str, dict[str, Any]]:
    """Classify CRS FTW tests by expected response status from YAML files."""

    classifications: dict[str, dict[str, Any]] = {}
    base = Path(root)
    if not base.exists():
        return classifications
    for path in sorted(base.rglob("*.y*ml")):
        classifications.update(_classify_ftw_yaml(path))
    return classifications


def summarize_ftw(
    raw: dict[str, Any],
    classifications: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a CRS conformance summary without estimating TP/FP ratios."""

    result = parse_go_ftw_result(raw)
    passed_ids = result["passed_ids"]
    failed_ids = result["failed_ids"]
    run = result["run"]
    passed = result["passed"]
    failed = result["failed"]

    expected_block = expected_allow = expected_unknown = 0
    passed_expected_block = failed_expected_block = 0
    passed_expected_allow = failed_expected_allow = 0

    for test_id in [*passed_ids, *failed_ids]:
        expected = classifications.get(test_id, {}).get("expected", "unknown")
        is_passed = test_id in passed_ids
        if expected == "block":
            expected_block += 1
            if is_passed:
                passed_expected_block += 1
            else:
                failed_expected_block += 1
        elif expected == "allow":
            expected_allow += 1
            if is_passed:
                passed_expected_allow += 1
            else:
                failed_expected_allow += 1
        else:
            expected_unknown += 1

    conformance = passed / run if run else None
    return {
        "crs_conformance_rate": round(conformance, 4) if conformance is not None else None,
        "crs_passed": passed,
        "crs_failed": failed,
        "crs_run": run,
        "skipped": result["skipped"],
        "expected_block_tests": expected_block,
        "expected_allow_tests": expected_allow,
        "expected_unknown_tests": expected_unknown,
        "passed_expected_block": passed_expected_block,
        "failed_expected_block": failed_expected_block,
        "passed_expected_allow": passed_expected_allow,
        "failed_expected_allow": failed_expected_allow,
        "failed_ids": failed_ids[:50],
        "note": (
            "go-ftw reports CRS regression conformance. Expected block/allow "
            "classes are derived from CRS YAML output.status; no TPR/FPR is estimated."
        ),
    }


def _classify_ftw_yaml(path: Path) -> dict[str, dict[str, Any]]:
    rule_id = path.stem
    cases: dict[str, dict[str, Any]] = {}
    current_id: str | None = None
    implicit_index = 0
    in_output = False
    output_indent = 0

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        test_id_match = re.match(r"(?:-\s*)?test_id:\s*['\"]?([^'\"\s]+)", stripped)
        if test_id_match:
            current_id = f"{rule_id}-{test_id_match.group(1)}"
            cases.setdefault(current_id, {"status": None, "expected": "unknown"})
            in_output = False
            continue

        if current_id is None and re.match(r"(?:-\s*)?test_title:\s*", stripped):
            implicit_index += 1
            current_id = f"{rule_id}-{implicit_index}"
            cases.setdefault(current_id, {"status": None, "expected": "unknown"})
            in_output = False
            continue

        if stripped == "output:" and current_id is not None:
            in_output = True
            output_indent = indent
            continue

        if in_output and indent <= output_indent:
            in_output = False

        status_match = re.match(r"status:\s*['\"]?(\d{3})", stripped)
        if in_output and current_id is not None and status_match:
            status = int(status_match.group(1))
            cases[current_id] = {
                "status": status,
                "expected": "block" if status == BLOCK_STATUS else "allow",
                "path": str(path),
            }

    return cases


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
