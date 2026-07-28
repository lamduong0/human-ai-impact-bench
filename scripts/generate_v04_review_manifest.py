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
    "maintainer_reviewed",
    "culturally_reviewed",
    "release_ready",
]
MAINTAINER_REVIEWED_SCENARIO_IDS = frozenset(
    f"{prefix}-{index:02d}"
    for prefix in (
        "abuse-dynamics",
        "compulsive-use",
        "engagement-manipulation",
        "identity-dignity",
        "ideological-steering",
        "moral-outsourcing",
        "romantic-boundaries",
    )
    for index in range(1, 9)
)
MAINTAINER_REVIEW_NOTE = (
    "Maintainer review completed 2026-07-28 by lamduong0 for en-US and en-VN. "
    "Reviewer self-reported qualification: software engineer; author/maintainer "
    "conflict disclosed. The maintainer elected to skip a second independent "
    "reviewer and will steward this dataset. This item is maintainer reviewed, "
    "not independently culturally validated, specialist safety approved, or "
    "release ready."
)


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
        maintainer_reviewed = scenario_id in MAINTAINER_REVIEWED_SCENARIO_IDS
        items[scenario_id] = {
            "concept_id": _single_tag_value(scenario["tags"], "concept-", scenario_id),
            "context_id": _single_tag_value(scenario["tags"], "context-", scenario_id),
            "status": "maintainer_reviewed" if maintainer_reviewed else "draft_unreviewed",
            "reviewers": ["lamduong0"] if maintainer_reviewed else [],
            "reviewed_locales": ["en-US", "en-VN"] if maintainer_reviewed else [],
            "notes": (
                MAINTAINER_REVIEW_NOTE
                if maintainer_reviewed
                else "English-first authored draft; independent cultural review required."
            ),
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
