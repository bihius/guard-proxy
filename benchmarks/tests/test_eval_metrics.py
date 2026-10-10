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
    crs_rule_paranoia_levels,
    ftw_exclusions,
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


def test_block_counts_deduplicate_snapshots_and_ignore_other_runs() -> None:
    first = _event(tx_id="same", case_id="sqli-1", interrupted=True, status=403)
    duplicate = json.loads(json.dumps(first))
    other_run = _event(tx_id="old", case_id="sqli-1", run_id="run-0", interrupted=True, status=403)

    counts = count_blocks([first, duplicate, other_run], "run-1")

    assert counts == {"corpus-wp.local": 1}


def test_ftw_classification_reads_crs_log_expectations(tmp_path: Path) -> None:
    # Real CRS tests mostly assert rule IDs, not a status code.
    tests_dir = tmp_path / "tests" / "REQUEST-941-APPLICATION-ATTACK-XSS"
    tests_dir.mkdir(parents=True)
    (tests_dir / "941100.yaml").write_text(
        """
rule_id: 941100
tests:
  - test_id: 1
    stages:
      - input:
          uri: "/?x=<script>"
        output:
          log:
            expect_ids: [941100]
  - test_id: 2
    stages:
      - input:
          uri: "/?x=hello"
        output:
          log:
            no_expect_ids: [941100]
  - test_id: 3
    stages:
      - input:
          method: "     GET"
        output:
          status: 400
""",
        encoding="utf-8",
    )

    classifications = classify_ftw_tests(tmp_path / "tests")
    summary = summarize_ftw(
        {"success": ["941100-1", "941100-3"], "failed": ["941100-2"], "ignored": []},
        classifications,
        {},
    )

    assert [classifications[f"941100-{i}"]["expected"] for i in (1, 2, 3)] == [
        "match",
        "no_match",
        "other",
    ]
    assert summary["crs_run"] == 3
    assert summary["expect_match_passed"] == 1
    assert summary["expect_no_match_failed"] == 1
    assert summary["expect_other_passed"] == 1


def test_ftw_exclusions_skip_rules_above_paranoia_and_response_rules(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "REQUEST-942-APPLICATION-ATTACK-SQLI.conf").write_text(
        """
SecRule TX:DETECTION_PARANOIA_LEVEL "@lt 1" "id:942011,phase:1,pass,nolog,skipAfter:END"
SecRule ARGS "@rx a" \\
    "id:942100,\\
    tag:'paranoia-level/1'"
SecRule TX:DETECTION_PARANOIA_LEVEL "@lt 2" "id:942013,phase:1,pass,nolog,skipAfter:END"
SecRule ARGS "@rx b" \\
    "id:942200,\\
    tag:'paranoia-level/2'"
SecRule ARGS "@rx c" "id:942210,phase:2,block"
""",
        encoding="utf-8",
    )
    levels = crs_rule_paranoia_levels(rules)
    classifications = {
        "942100-1": {"rule_id": "942100", "expected": "match", "phase": "request"},
        "942200-1": {"rule_id": "942200", "expected": "match", "phase": "request"},
        "942210-1": {"rule_id": "942210", "expected": "match", "phase": "request"},
        "951100-1": {"rule_id": "951100", "expected": "match", "phase": "response"},
    }

    assert levels == {"942100": 1, "942200": 2, "942210": 2}
    assert sorted(ftw_exclusions(classifications, levels, 1)) == [
        "^942200-",
        "^942210-",
        "^951100-",
    ]
    assert sorted(ftw_exclusions(classifications, levels, 2)) == ["^951100-"]


def test_load_json_lines_ignores_malformed_lines(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    path.write_text('{"ok": true}\nnot-json\n{"ok": false}\n', encoding="utf-8")

    assert load_json_lines(path) == [{"ok": True}, {"ok": False}]
