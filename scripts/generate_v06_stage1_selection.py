#!/usr/bin/env python3
"""Freeze the reviewed 210-record v0.6 Stage 1 selection and digests."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import ValidationError, load_scenarios

ROOT = Path(__file__).resolve().parents[1]
V06_DIR = ROOT / "data" / "scenarios" / "v0.6"
COVERAGE_CONFIG = ROOT / "configs" / "scenario-coverage-standard.json"
OUTPUT_PATH = V06_DIR / "stage1-selection.json"
_NUMBER_SUFFIX = re.compile(r"-(\d{2})$")


def _digest(scenario: dict[str, Any]) -> str:
    payload = json.dumps(
        scenario,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def build_selection() -> dict[str, Any]:
    config = json.loads(COVERAGE_CONFIG.read_text(encoding="utf-8"))["v0.6"]
    stage1 = config["stage1_foundation"]
    categories = set(stage1["categories"])
    records_per_category = stage1["records_per_category"]
    scenarios = [
        scenario
        for path in sorted((V06_DIR / "en").glob("*.jsonl"))
        for scenario in load_scenarios(path)
        if scenario["category"] in categories
        and (
            (match := _NUMBER_SUFFIX.search(scenario["scenario_id"])) is not None
            and int(match.group(1)) <= records_per_category
        )
    ]
    category_counts = Counter(scenario["category"] for scenario in scenarios)
    if set(category_counts) != categories or any(
        category_counts[category] != records_per_category for category in categories
    ):
        raise ValidationError("v0.6 Stage 1 selection is incomplete")
    if len({scenario["scenario_id"] for scenario in scenarios}) != len(scenarios):
        raise ValidationError("v0.6 Stage 1 selection contains duplicate IDs")

    items = [
        {
            "language": scenario["language"],
            "scenario_id": scenario["scenario_id"],
            "category": scenario["category"],
            "scenario_sha256": _digest(scenario),
        }
        for scenario in scenarios
    ]
    return {
        "selection_version": "0.1",
        "benchmark_version": "0.6",
        "selection_rule_id": "v06-stage1-seven-categories-records-01-through-30",
        "scenario_count": len(items),
        "category_counts": dict(sorted(category_counts.items())),
        "items": sorted(
            items,
            key=lambda item: (item["category"], item["scenario_id"]),
        ),
        "limitations": [
            "This freezes reviewed authored data, not cultural validity or model evidence.",
            "Later v0.6 checkpoint records are not part of the Stage 1 approval.",
        ],
    }


def main() -> int:
    OUTPUT_PATH.write_text(
        json.dumps(build_selection(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
