#!/usr/bin/env python3
"""Generate a digest-bound draft review manifest for one v0.6 language."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import ValidationError, load_scenarios

ROOT = Path(__file__).resolve().parents[1]
V06_DIR = ROOT / "data" / "scenarios" / "v0.6"
STAGE1_SELECTION = V06_DIR / "stage1-selection.json"
ALLOWED_STATUSES = [
    "draft_unreviewed",
    "in_review",
    "changes_requested",
    "maintainer_reviewed",
    "culturally_reviewed",
    "release_ready",
]
REVIEW_NOTE = (
    "v0.6 staged authoring. Requires construct and locale review; source review "
    "status does not transfer to this adapted or newly authored record."
)
MAINTAINER_REVIEW_NOTE = (
    "Maintainer review approved 2026-07-28 by lamduong0 for en-US and en-VN. "
    "Reviewer self-reported qualification: software engineer; author/maintainer "
    "conflict disclosed. The maintainer elected to skip a second independent "
    "reviewer and will steward this dataset. This item is maintainer reviewed, "
    "not independently culturally validated, specialist safety approved, or "
    "release ready."
)
CHECKPOINT_REVIEWED_LOCALES = {
    "en": ["en-US", "en-VN"],
    "vi": ["vi-VN"],
}


def _checkpoint_review_note(language: str) -> str:
    locales = " and ".join(CHECKPOINT_REVIEWED_LOCALES[language])
    return (
        f"Full-checkpoint maintainer review approved 2026-07-29 by lamduong0 "
        f"for {locales}. Reviewer self-reported qualification: software "
        "engineer; author/maintainer conflict disclosed. The maintainer elected "
        "to skip a second independent reviewer and will steward this dataset. "
        "This item is maintainer reviewed, not independently culturally "
        "validated, specialist safety approved, or release ready."
    )


def _digest(scenario: dict[str, Any]) -> str:
    payload = json.dumps(
        scenario,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _single_tag(tags: list[str], prefix: str, scenario_id: str) -> str:
    values = [tag.removeprefix(prefix) for tag in tags if tag.startswith(prefix)]
    if len(values) != 1 or not values[0]:
        raise ValidationError(
            f"{scenario_id} must have exactly one non-empty {prefix.rstrip('-')} tag"
        )
    return values[0]


def _stage1_approved_digests() -> dict[tuple[str, str], str]:
    selection = json.loads(STAGE1_SELECTION.read_text(encoding="utf-8"))
    return {
        (item["language"], item["scenario_id"]): item["scenario_sha256"]
        for item in selection["items"]
    }


def build_manifest(
    language: str,
    existing_manifest: dict[str, Any] | None = None,
    *,
    maintainer_review_stage1: bool = False,
    maintainer_review_all: bool = False,
) -> dict[str, Any]:
    language_dir = V06_DIR / language
    scenarios = [
        scenario
        for path in sorted(language_dir.glob("*.jsonl"))
        for scenario in load_scenarios(path)
    ]
    if not scenarios:
        raise ValidationError(f"no v0.6 {language} scenarios found")
    if {scenario["benchmark_version"] for scenario in scenarios} != {"0.6"}:
        raise ValidationError(f"v0.6 {language} directory contains another benchmark version")
    if {scenario["language"] for scenario in scenarios} != {language}:
        raise ValidationError(f"v0.6 {language} directory contains another language")

    items: dict[str, dict[str, Any]] = {}
    stage1_approved_digests = _stage1_approved_digests() if maintainer_review_stage1 else {}
    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        if scenario_id in items:
            raise ValidationError(f"duplicate v0.6 {language} scenario ID: {scenario_id}")
        if "requires-cultural-review" not in scenario["tags"]:
            raise ValidationError(f"{scenario_id} is missing requires-cultural-review")
        item = {
            "concept_id": _single_tag(scenario["tags"], "concept-", scenario_id),
            "context_id": _single_tag(scenario["tags"], "context-", scenario_id),
            "scenario_digest": _digest(scenario),
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
            and existing_item.get("concept_id") == item["concept_id"]
            and existing_item.get("context_id") == item["context_id"]
            and existing_item.get("scenario_digest") == item["scenario_digest"]
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
                    "reviewed_locales": CHECKPOINT_REVIEWED_LOCALES[language],
                    "notes": _checkpoint_review_note(language),
                }
            )
        elif (
            maintainer_review_stage1
            and stage1_approved_digests.get((language, scenario_id)) == item["scenario_digest"]
        ):
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
        "benchmark_version": "0.6",
        "language": language,
        "scenario_count": len(scenarios),
        "allowed_statuses": ALLOWED_STATUSES,
        "items": dict(sorted(items.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("en", "vi"), required=True)
    parser.add_argument(
        "--mark-stage1-maintainer-reviewed",
        action="store_true",
        help="Record the disclosed maintainer approval for current Stage 1 categories.",
    )
    parser.add_argument(
        "--mark-all-maintainer-reviewed",
        action="store_true",
        help="Record the disclosed maintainer approval for the complete v0.6 checkpoint.",
    )
    args = parser.parse_args()

    output_path = V06_DIR / args.language / "review-status.json"
    existing_manifest = None
    if output_path.exists():
        existing_manifest = json.loads(output_path.read_text(encoding="utf-8"))
    output_path.write_text(
        json.dumps(
            build_manifest(
                args.language,
                existing_manifest=existing_manifest,
                maintainer_review_stage1=args.mark_stage1_maintainer_reviewed,
                maintainer_review_all=args.mark_all_maintainer_reviewed,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
