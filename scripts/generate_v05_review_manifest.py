#!/usr/bin/env python3
"""Generate the review manifest for the authored v0.5 research scenarios."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import ValidationError, load_scenarios

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIR = ROOT / "data" / "scenarios" / "v0.5"
OUTPUT_PATH = SCENARIOS_DIR / "review-status.json"
ALLOWED_STATUSES = [
    "draft_unreviewed",
    "in_review",
    "changes_requested",
    "maintainer_reviewed",
    "culturally_reviewed",
    "release_ready",
]
REVIEW_NOTE = (
    "English-first v0.5 research draft. Requires construct, cultural, and "
    "locale-specific review before any reviewed or release-ready claim."
)
MAINTAINER_REVIEW_NOTE = (
    "Maintainer review completed 2026-07-28 by lamduong0 for en-US and en-VN. "
    "Reviewer self-reported qualification: software engineer; author/maintainer "
    "conflict disclosed. The maintainer elected to skip a second independent "
    "reviewer and will steward this dataset. This item is maintainer reviewed, "
    "not independently culturally validated, specialist safety approved, or "
    "release ready."
)


def _scenario_digest(scenario: dict[str, Any]) -> str:
    payload = json.dumps(
        scenario,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _single_tag_value(tags: list[str], prefix: str, scenario_id: str) -> str:
    values = [tag.removeprefix(prefix) for tag in tags if tag.startswith(prefix)]
    if len(values) != 1 or not values[0]:
        raise ValidationError(
            f"{scenario_id} must have exactly one non-empty {prefix.rstrip('-')} tag"
        )
    return values[0]


def build_manifest(
    existing_manifest: dict[str, Any] | None = None,
    *,
    maintainer_review_all: bool = False,
) -> dict[str, Any]:
    scenarios = [
        scenario
        for path in sorted(SCENARIOS_DIR.glob("*.jsonl"))
        for scenario in load_scenarios(path)
    ]
    items: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        if scenario_id in items:
            raise ValidationError(f"duplicate scenario_id in v0.5 scenarios: {scenario_id}")
        if "requires-cultural-review" not in scenario["tags"]:
            raise ValidationError(f"{scenario_id} is missing requires-cultural-review")
        concept_id = _single_tag_value(scenario["tags"], "concept-", scenario_id)
        context_id = _single_tag_value(scenario["tags"], "context-", scenario_id)
        scenario_digest = _scenario_digest(scenario)
        item = {
            "concept_id": concept_id,
            "context_id": context_id,
            "scenario_digest": scenario_digest,
            "status": "draft_unreviewed",
            "reviewers": [],
            "reviewed_locales": [],
            "notes": REVIEW_NOTE,
        }
        existing_item = (
            existing_manifest.get("items", {}).get(scenario_id)
            if isinstance(existing_manifest, dict)
            and isinstance(existing_manifest.get("items"), dict)
            else None
        )
        if (
            isinstance(existing_item, dict)
            and existing_item.get("concept_id") == concept_id
            and existing_item.get("context_id") == context_id
            and existing_item.get("scenario_digest") == scenario_digest
            and existing_item.get("status") in ALLOWED_STATUSES
            and isinstance(existing_item.get("reviewers"), list)
            and isinstance(existing_item.get("reviewed_locales"), list)
            and isinstance(existing_item.get("notes"), str)
        ):
            for field in ("status", "reviewers", "reviewed_locales", "notes"):
                item[field] = existing_item[field]
        if maintainer_review_all:
            item.update(
                {
                    "status": "maintainer_reviewed",
                    "reviewers": ["lamduong0"],
                    "reviewed_locales": ["en-US", "en-VN"],
                    "notes": MAINTAINER_REVIEW_NOTE,
                }
            )
        items[scenario_id] = item

    return {
        "manifest_version": "0.1",
        "benchmark_version": "0.5",
        "language": "en",
        "scenario_count": len(scenarios),
        "allowed_statuses": ALLOWED_STATUSES,
        "items": dict(sorted(items.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mark-maintainer-reviewed",
        action="store_true",
        help="Record the disclosed maintainer review for every current v0.5 item.",
    )
    args = parser.parse_args()

    existing_manifest = None
    if OUTPUT_PATH.exists():
        try:
            existing_manifest = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"cannot preserve existing review manifest: invalid JSON: {exc.msg}"
            ) from exc
    OUTPUT_PATH.write_text(
        json.dumps(
            build_manifest(
                existing_manifest=existing_manifest,
                maintainer_review_all=args.mark_maintainer_reviewed,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
