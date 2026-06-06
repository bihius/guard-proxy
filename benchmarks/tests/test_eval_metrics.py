from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

RUNNERS = Path(__file__).resolve().parents[1] / "lab" / "runners"
sys.path.insert(0, str(RUNNERS))

from eval_metrics import (  # noqa: E402
    classify_ftw_tests,
    count_blocks,
    load_json_lines,
    summarize_ftw,
    summarize_tagged_corpus,
)


def _event(
    *,
    tx_id: str,
    case_id: str,
    scenario: str = "corpus-wp.local",
    run_id: str = "run-1",
    interrupted: bool = False,
    status: int = 200,
) -> dict[str, Any]:
    return {
        "transaction": {
            "id": tx_id,
            "is_interrupted": interrupted,
            "request": {
                "method": "GET",
                "uri": "/",
                "headers": {
                    "Host": ["wp.local"],
                    "X-GP-Eval-Run": [run_id],
                    "X-GP-Eval-Scenario": [scenario],
                    "X-GP-Eval-Case": [case_id],
                },
            },
            "response": {"status": status},
        }
    }


def test_tagged_corpus_computes_tp_fn_tn_fp_with_missing_allow_events() -> None:
    cases = [
        {"case_id": "benign-1", "expected": "allow"},
        {"case_id": "benign-2", "expected": "allow"},
        {"case_id": "sqli-1", "expected": "block"},
        {"case_id": "xss-1", "expected": "block"},
    ]
    events = [
        _event(tx_id="1", case_id="benign-2", interrupted=True, status=403),
        _event(tx_id="2", case_id="sqli-1", interrupted=True, status=403),
    ]

    summary = summarize_tagged_corpus(
        cases,
        events,
        run_id="run-1",
        scenario="corpus-wp.local",
    )

    assert summary["true_negative"] == 1
    assert summary["false_positive"] == 1
    assert summary["true_positive"] == 1
    assert summary["false_negative"] == 1
    assert summary["tpr"] == 0.5
    assert summary["fpr"] == 0.5


def test_block_counts_deduplicate_cumulative_audit_snapshots() -> None:
    first = _event(tx_id="same", case_id="sqli-1", interrupted=True, status=403)
    duplicate = json.loads(json.dumps(first))

    counts = count_blocks([first, duplicate])

    assert counts["by_vhost"] == {"wp.local": 1}
    assert counts["by_scenario"] == {"corpus-wp.local": 1}


def test_ftw_yaml_classification_and_summary(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "941100.yaml").write_text(
        """
meta:
  enabled: true
tests:
  - test_id: 1
    stages:
      - stage:
          output:
            status: 403
  - test_id: 2
    stages:
      - stage:
          output:
            status: 200
""",
        encoding="utf-8",
    )

    classifications = classify_ftw_tests(tests_dir)
    summary = summarize_ftw(
        {
            "run": 2,
            "success": ["941100-1"],
            "failed": ["941100-2"],
            "skipped": [],
        },
        classifications,
    )

    assert classifications["941100-1"]["expected"] == "block"
    assert classifications["941100-2"]["expected"] == "allow"
    assert summary["crs_conformance_rate"] == 0.5
    assert summary["expected_block_tests"] == 1
    assert summary["expected_allow_tests"] == 1
    assert summary["passed_expected_block"] == 1
    assert summary["failed_expected_allow"] == 1


def test_load_json_lines_ignores_malformed_lines(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    path.write_text('{"ok": true}\nnot-json\n{"ok": false}\n', encoding="utf-8")

    assert load_json_lines(path) == [{"ok": True}, {"ok": False}]
