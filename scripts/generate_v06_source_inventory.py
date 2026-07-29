#!/usr/bin/env python3
"""Generate the immutable-source inventory used to author v0.6."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import ValidationError, load_scenarios

try:
    from scripts.validate_cultural_review import validate_review_manifest
except ModuleNotFoundError:  # Direct execution places scripts/ on sys.path.
    from validate_cultural_review import validate_review_manifest

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "scenarios" / "v0.6"
OUTPUT_PATH = OUTPUT_DIR / "source-inventory.json"
COVERAGE_CONFIG = ROOT / "configs" / "scenario-coverage-standard.json"
SOURCE_VERSIONS = ("v0.1", "v0.2", "v0.3", "v0.4")


def _digest(record: dict[str, Any]) -> str:
    payload = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _review_statuses(version_dir: Path) -> dict[str, str]:
    manifest_path = version_dir / "review-status.json"
    if not manifest_path.exists():
        return {}
    validate_review_manifest(version_dir, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {scenario_id: item["status"] for scenario_id, item in manifest["items"].items()}


def build_inventory() -> dict[str, Any]:
    coverage = json.loads(COVERAGE_CONFIG.read_text(encoding="utf-8"))["v0.6"]
    expected_categories = set(coverage["categories"])
    items: list[dict[str, Any]] = []
    category_records: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for source_version in SOURCE_VERSIONS:
        version_dir = ROOT / "data" / "scenarios" / source_version
        review_statuses = _review_statuses(version_dir)
        for path in sorted(version_dir.glob("*.jsonl")):
            for scenario in load_scenarios(path):
                source_key = f"{source_version}:{scenario['language']}:{scenario['scenario_id']}"
                item = {
                    "source_key": source_key,
                    "source_version": source_version.removeprefix("v"),
                    "source_path": str(path.relative_to(ROOT)),
                    "source_scenario_id": scenario["scenario_id"],
                    "language": scenario["language"],
                    "category": scenario["category"],
                    "risk_level": scenario["risk_level"],
                    "dimensions": scenario["dimensions"],
                    "tags": scenario["tags"],
                    "review_status": review_statuses.get(
                        scenario["scenario_id"],
                        "no_review_manifest",
                    ),
                    "content_sha256": _digest(scenario),
                }
                items.append(item)
                category_records[scenario["category"]].append(item)

    actual_categories = set(category_records)
    if actual_categories != expected_categories:
        missing = sorted(expected_categories - actual_categories)
        extra = sorted(actual_categories - expected_categories)
        raise ValidationError(f"v0.6 source category mismatch: missing={missing}, extra={extra}")
    source_keys = [item["source_key"] for item in items]
    if len(source_keys) != len(set(source_keys)):
        raise ValidationError("v0.6 source inventory contains duplicate source keys")

    categories: dict[str, dict[str, Any]] = {}
    for category, records in sorted(category_records.items()):
        categories[category] = {
            "source_record_count": len(records),
            "language_counts": dict(
                sorted(Counter(record["language"] for record in records).items())
            ),
            "version_counts": dict(
                sorted(Counter(record["source_version"] for record in records).items())
            ),
            "review_status_counts": dict(
                sorted(Counter(record["review_status"] for record in records).items())
            ),
            "source_keys": sorted(record["source_key"] for record in records),
        }

    return {
        "inventory_version": "0.1",
        "target_benchmark_version": "0.6",
        "source_versions": [version.removeprefix("v") for version in SOURCE_VERSIONS],
        "source_record_count": len(items),
        "category_count": len(categories),
        "review_status_counts": dict(
            sorted(Counter(item["review_status"] for item in items).items())
        ),
        "categories": categories,
        "items": sorted(items, key=lambda item: item["source_key"]),
        "notes": [
            "This is a read-only lineage inventory; it does not modify released source data.",
            "A source review status does not transfer to an adapted or newly authored v0.6 record.",
            "v0.1 and v0.2 have no per-scenario review manifest in the repository.",
        ],
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(build_inventory(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
