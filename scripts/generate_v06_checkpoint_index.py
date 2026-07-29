#!/usr/bin/env python3
"""Generate the frozen 1,200-record v0.6 first-checkpoint selection index."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import ValidationError, load_scenarios

try:
    from scripts.validate_cultural_review import validate_review_manifest
except ModuleNotFoundError:  # Direct execution places scripts/ on sys.path.
    from validate_cultural_review import validate_review_manifest

ROOT = Path(__file__).resolve().parents[1]
V06_DIR = ROOT / "data" / "scenarios" / "v0.6"
COVERAGE_CONFIG = ROOT / "configs" / "scenario-coverage-standard.json"
LINEAGE_INDEX = V06_DIR / "lineage-index.json"
OUTPUT_PATH = V06_DIR / "checkpoint-index.json"


def _sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scenario_digest(scenario: dict[str, Any]) -> str:
    payload = json.dumps(
        scenario,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _single_tag(scenario: dict[str, Any], prefix: str) -> str:
    values = [tag.removeprefix(prefix) for tag in scenario["tags"] if tag.startswith(prefix)]
    if len(values) != 1 or not values[0]:
        raise ValidationError(
            f"{scenario['scenario_id']} must have exactly one non-empty {prefix.rstrip('-')} tag"
        )
    return values[0]


def _load_language(language: str) -> list[dict[str, Any]]:
    language_dir = V06_DIR / language
    return [
        scenario
        for path in sorted(language_dir.glob("*.jsonl"))
        for scenario in load_scenarios(path)
    ]


def build_index() -> dict[str, Any]:
    config = json.loads(COVERAGE_CONFIG.read_text(encoding="utf-8"))["v0.6"]
    categories = set(config["categories"])
    bilingual = set(config["bilingual_categories"])
    english_first = set(config["english_first_categories"])
    records_per_category = config["first_complete_checkpoint_records_per_category"]
    records_per_bilingual_language = config[
        "first_complete_checkpoint_records_per_language_in_bilingual_category"
    ]

    scenarios = _load_language("en") + _load_language("vi")
    identities = [(scenario["language"], scenario["scenario_id"]) for scenario in scenarios]
    if len(identities) != len(set(identities)):
        raise ValidationError("v0.6 checkpoint contains duplicate language/scenario identities")
    if {scenario["benchmark_version"] for scenario in scenarios} != {"0.6"}:
        raise ValidationError("v0.6 checkpoint contains another benchmark version")
    if {scenario["category"] for scenario in scenarios} != categories:
        raise ValidationError("v0.6 checkpoint category set does not match coverage config")

    category_counts = Counter(scenario["category"] for scenario in scenarios)
    if any(category_counts[category] != records_per_category for category in categories):
        raise ValidationError("v0.6 checkpoint does not have 50 physical records per category")

    language_category_counts = Counter(
        (scenario["language"], scenario["category"]) for scenario in scenarios
    )
    for category in bilingual:
        for language in ("en", "vi"):
            if language_category_counts[(language, category)] != records_per_bilingual_language:
                raise ValidationError(
                    f"{category} does not have {records_per_bilingual_language} {language} records"
                )
    for category in english_first:
        if language_category_counts[("en", category)] != records_per_category:
            raise ValidationError(f"{category} does not have {records_per_category} EN records")
        if language_category_counts[("vi", category)]:
            raise ValidationError(f"{category} unexpectedly contains Vietnamese records")

    expected_total = config["first_complete_checkpoint_total_records"]
    if len(scenarios) != expected_total:
        raise ValidationError(
            f"v0.6 checkpoint has {len(scenarios)} records; expected {expected_total}"
        )

    review_items: dict[tuple[str, str], dict[str, Any]] = {}
    for language in ("en", "vi"):
        manifest_path = V06_DIR / language / "review-status.json"
        validate_review_manifest(V06_DIR / language, manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        review_items.update(
            {(language, scenario_id): item for scenario_id, item in manifest["items"].items()}
        )

    lineage = json.loads(LINEAGE_INDEX.read_text(encoding="utf-8"))
    lineage_items = {
        (item["target_language"], item["target_scenario_id"]): item for item in lineage["items"]
    }
    if set(lineage_items) != set(identities):
        raise ValidationError("v0.6 lineage index does not cover the checkpoint selection")

    items: list[dict[str, Any]] = []
    for scenario in scenarios:
        identity = (scenario["language"], scenario["scenario_id"])
        scenario_sha256 = _scenario_digest(scenario)
        lineage_item = lineage_items[identity]
        review_item = review_items[identity]
        if lineage_item["target_scenario_sha256"] != scenario_sha256:
            raise ValidationError(f"{identity} lineage digest does not match checkpoint scenario")
        if review_item["scenario_digest"] != scenario_sha256:
            raise ValidationError(f"{identity} review digest does not match checkpoint scenario")
        items.append(
            {
                "language": scenario["language"],
                "scenario_id": scenario["scenario_id"],
                "category": scenario["category"],
                "risk_level": scenario["risk_level"],
                "concept_id": _single_tag(scenario, "concept-"),
                "context_id": _single_tag(scenario, "context-"),
                "scenario_sha256": scenario_sha256,
                "derivation": lineage_item["derivation"],
                "review_status": review_item["status"],
            }
        )

    review_status_counts = Counter(item["review_status"] for item in items)
    return {
        "index_version": "0.1",
        "benchmark_version": "0.6",
        "checkpoint": "first_complete_50_per_category",
        "selection_rule_id": "v06-first-complete-checkpoint-all-records",
        "scenario_count": len(items),
        "category_count": len(categories),
        "category_counts": dict(sorted(category_counts.items())),
        "language_counts": dict(sorted(Counter(item["language"] for item in items).items())),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "coverage_config_sha256": _sha256_bytes(COVERAGE_CONFIG),
        "lineage_index_sha256": _sha256_bytes(LINEAGE_INDEX),
        "review_manifest_sha256": {
            language: _sha256_bytes(V06_DIR / language / "review-status.json")
            for language in ("en", "vi")
        },
        "items": sorted(
            items,
            key=lambda item: (
                item["language"],
                item["category"],
                item["scenario_id"],
            ),
        ),
        "limitations": [
            "The index freezes authored coverage, not cultural validity or human-impact evidence.",
            "Maintainer review of earlier Stage 1 records does not transfer to new records.",
            "Automated benchmark runs over this checkpoint remain PREVIEW evidence.",
        ],
    }


def main() -> int:
    OUTPUT_PATH.write_text(
        json.dumps(build_index(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
