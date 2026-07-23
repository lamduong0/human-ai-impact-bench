#!/usr/bin/env python3
"""Generate the cultural-review manifest for the authored v0.4 scenarios."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import ValidationError, load_scenarios

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIR = ROOT / "data" / "scenarios" / "v0.4"
OUTPUT_PATH = SCENARIOS_DIR / "review-status.json"
ALLOWED_STATUSES = [
    "draft_unreviewed",
    "in_review",
    "changes_requested",
    "culturally_reviewed",
    "release_ready",
]


def _single_tag_value(tags: list[str], prefix: str, scenario_id: str) -> str:
    values = [tag.removeprefix(prefix) for tag in tags if tag.startswith(prefix)]
    if len(values) != 1 or not values[0]:
        raise ValidationError(
            f"{scenario_id} must have exactly one non-empty {prefix.rstrip('-')} tag"
        )
    return values[0]


def build_manifest() -> dict[str, Any]:
    scenarios = [
        scenario
        for path in sorted(SCENARIOS_DIR.glob("*.jsonl"))
        for scenario in load_scenarios(path)
    ]
    items: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        if scenario_id in items:
            raise ValidationError(f"duplicate scenario_id in v0.4 scenarios: {scenario_id}")
        if "requires-cultural-review" not in scenario["tags"]:
            raise ValidationError(f"{scenario_id} is missing requires-cultural-review")
        items[scenario_id] = {
            "concept_id": _single_tag_value(scenario["tags"], "concept-", scenario_id),
            "context_id": _single_tag_value(scenario["tags"], "context-", scenario_id),
            "status": "draft_unreviewed",
            "reviewers": [],
            "reviewed_locales": [],
            "notes": ("English-first authored draft; independent cultural review required."),
        }

    return {
        "manifest_version": "0.1",
        "benchmark_version": "0.4",
        "language": "en",
        "scenario_count": len(scenarios),
        "allowed_statuses": ALLOWED_STATUSES,
        "items": dict(sorted(items.items())),
    }


def main() -> int:
    OUTPUT_PATH.write_text(
        json.dumps(build_manifest(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
