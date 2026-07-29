#!/usr/bin/env python3
"""Generate and validate v0.6 scenario lineage without changing source releases."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import ValidationError, load_scenarios

ROOT = Path(__file__).resolve().parents[1]
V06_DIR = ROOT / "data" / "scenarios" / "v0.6"
INVENTORY_PATH = V06_DIR / "source-inventory.json"
OUTPUT_PATH = V06_DIR / "lineage-index.json"
LANGUAGE_DIRS = ("en", "vi")
LEGACY_FIELDS = {
    "benchmark_version",
    "scenario_id",
    "language",
    "title",
    "category",
    "risk_level",
    "context",
    "persona",
    "initial_prompt",
    "follow_up_prompts",
    "expected_behaviors",
    "failure_modes",
    "dimensions",
    "tags",
}


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
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


def _source_version(tag_value: str) -> str:
    if not tag_value.startswith("v") or "-" not in tag_value:
        raise ValidationError(f"invalid source-version tag value: {tag_value}")
    return tag_value.removeprefix("v").replace("-", ".", 1)


def _source_records() -> dict[str, dict[str, Any]]:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    records_by_path: dict[Path, list[dict[str, Any]]] = {}
    records: dict[str, dict[str, Any]] = {}
    for item in inventory["items"]:
        path = ROOT / item["source_path"]
        if path not in records_by_path:
            records_by_path[path] = load_scenarios(path)
        source = next(
            scenario
            for scenario in records_by_path[path]
            if scenario["scenario_id"] == item["source_scenario_id"]
            and scenario["language"] == item["language"]
        )
        source_digest = _digest(source)
        if source_digest != item["content_sha256"]:
            raise ValidationError(
                f"{item['source_key']} content no longer matches the source inventory"
            )
        records[item["source_key"]] = {
            "scenario": source,
            "source_path": item["source_path"],
        }
    return records


def _v06_scenarios() -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    for language in LANGUAGE_DIRS:
        for path in sorted((V06_DIR / language).glob("*.jsonl")):
            for scenario in load_scenarios(path):
                scenario_id = scenario["scenario_id"]
                if scenario["benchmark_version"] != "0.6":
                    raise ValidationError(
                        f"{scenario_id} in the v0.6 tree has benchmark_version "
                        f"{scenario['benchmark_version']!r}"
                    )
                if scenario["language"] != language:
                    raise ValidationError(
                        f"{scenario_id} language {scenario['language']!r} does not match "
                        f"directory {language!r}"
                    )
                scenarios.append(scenario)
    return scenarios


def build_index() -> dict[str, Any]:
    inventory_sha256 = hashlib.sha256(INVENTORY_PATH.read_bytes()).hexdigest()
    source_records = _source_records()
    scenarios = _v06_scenarios()
    items: list[dict[str, Any]] = []

    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        if set(scenario) != LEGACY_FIELDS:
            raise ValidationError(f"{scenario_id} must use exactly the legacy 14 fields")
        concept_id = _single_tag(scenario["tags"], "concept-", scenario_id)
        context_id = _single_tag(scenario["tags"], "context-", scenario_id)
        derivation = _single_tag(scenario["tags"], "derivation-", scenario_id)
        if derivation not in {"adapted", "authored-new"}:
            raise ValidationError(f"{scenario_id} has unsupported derivation {derivation!r}")

        item: dict[str, Any] = {
            "target_scenario_id": scenario_id,
            "target_language": scenario["language"],
            "target_category": scenario["category"],
            "target_scenario_sha256": _digest(scenario),
            "derivation": derivation.replace("-", "_"),
            "concept_id": concept_id,
            "context_id": context_id,
            "review_status_reset": True,
        }
        if derivation == "adapted":
            version_tag = _single_tag(scenario["tags"], "source-version-", scenario_id)
            source_scenario_id = _single_tag(
                scenario["tags"],
                "source-scenario-",
                scenario_id,
            )
            source_version = _source_version(version_tag)
            source_key = f"v{source_version}:{scenario['language']}:{source_scenario_id}"
            source_entry = source_records.get(source_key)
            if source_entry is None:
                raise ValidationError(f"{scenario_id} references unknown source key {source_key}")
            source = source_entry["scenario"]
            changed_fields = sorted(
                field for field in LEGACY_FIELDS if scenario[field] != source[field]
            )
            if changed_fields != ["benchmark_version", "scenario_id", "tags"]:
                raise ValidationError(
                    f"{scenario_id} adapted source changed unexpected fields: {changed_fields}"
                )
            item.update(
                {
                    "source_key": source_key,
                    "source_version": source_version,
                    "source_path": source_entry["source_path"],
                    "source_scenario_id": source_scenario_id,
                    "source_language": source["language"],
                    "source_content_sha256": _digest(source),
                    "changed_fields": changed_fields,
                    "adaptation_note": (
                        "Substantive scenario content preserved; benchmark version, "
                        "scenario identity, and lineage tags changed."
                    ),
                }
            )
        else:
            if any(
                tag.startswith(("source-version-", "source-scenario-")) for tag in scenario["tags"]
            ):
                raise ValidationError(
                    f"{scenario_id} authored-new record must not claim a source record"
                )
            item.update(
                {
                    "source_key": None,
                    "source_version": None,
                    "source_path": None,
                    "source_scenario_id": None,
                    "source_language": None,
                    "source_content_sha256": None,
                    "changed_fields": [],
                    "adaptation_note": "New v0.6 scenario authoring.",
                }
            )
        items.append(item)

    target_keys = [f"{item['target_language']}:{item['target_scenario_id']}" for item in items]
    if len(target_keys) != len(set(target_keys)):
        raise ValidationError("v0.6 lineage index contains duplicate target identities")

    return {
        "index_version": "0.1",
        "benchmark_version": "0.6",
        "selection_rule_id": "v06-staged-30-50-80-100",
        "source_inventory_sha256": inventory_sha256,
        "scenario_count": len(items),
        "category_counts": dict(sorted(Counter(item["target_category"] for item in items).items())),
        "language_counts": dict(sorted(Counter(item["target_language"] for item in items).items())),
        "derivation_counts": dict(sorted(Counter(item["derivation"] for item in items).items())),
        "items": sorted(
            items,
            key=lambda item: (
                item["target_language"],
                item["target_category"],
                item["target_scenario_id"],
            ),
        ),
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
