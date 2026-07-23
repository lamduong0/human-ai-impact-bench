#!/usr/bin/env python3
"""Validate scenario coverage and claims in a cultural-review manifest."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import ValidationError, load_scenarios

REVIEWED_STATUSES = {"culturally_reviewed", "release_ready"}


def _load_manifest(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {source}") from exc
    except OSError as exc:
        raise ValidationError(f"could not read {source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{source}: invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValidationError("review manifest must be a JSON object")
    return value


def _string_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValidationError(f"{label} must be an array of non-empty strings")
    if len(value) != len(set(value)):
        raise ValidationError(f"{label} items must be unique")
    return value


def validate_review_manifest(
    scenarios_path: str | Path,
    manifest_path: str | Path,
) -> dict[str, Any]:
    scenarios = load_scenarios(scenarios_path)
    manifest = _load_manifest(manifest_path)
    required = {
        "manifest_version",
        "benchmark_version",
        "language",
        "scenario_count",
        "allowed_statuses",
        "items",
    }
    missing = sorted(required - set(manifest))
    unexpected = sorted(set(manifest) - required)
    if missing:
        raise ValidationError(f"review manifest missing fields: {', '.join(missing)}")
    if unexpected:
        raise ValidationError(f"review manifest unexpected fields: {', '.join(unexpected)}")
    if manifest["manifest_version"] != "0.1":
        raise ValidationError("review manifest_version must be '0.1'")
    if not isinstance(manifest["benchmark_version"], str):
        raise ValidationError("review benchmark_version must be a string")
    if not isinstance(manifest["language"], str):
        raise ValidationError("review language must be a string")
    if not isinstance(manifest["scenario_count"], int) or isinstance(
        manifest["scenario_count"], bool
    ):
        raise ValidationError("review scenario_count must be an integer")
    allowed_statuses = set(_string_array(manifest["allowed_statuses"], "allowed_statuses"))
    if not REVIEWED_STATUSES <= allowed_statuses:
        raise ValidationError("allowed_statuses must include reviewed and release-ready states")
    if not isinstance(manifest["items"], dict):
        raise ValidationError("review items must be an object")

    scenario_ids = {scenario["scenario_id"] for scenario in scenarios}
    if len(scenario_ids) != len(scenarios):
        raise ValidationError("scenario IDs must be unique in a single-language review set")
    if set(manifest["items"]) != scenario_ids:
        missing_items = sorted(scenario_ids - set(manifest["items"]))
        extra_items = sorted(set(manifest["items"]) - scenario_ids)
        details = []
        if missing_items:
            details.append(f"missing review items: {missing_items}")
        if extra_items:
            details.append(f"unknown review items: {extra_items}")
        raise ValidationError("; ".join(details))
    if manifest["scenario_count"] != len(scenarios):
        raise ValidationError("review scenario_count does not match scenario data")
    if {scenario["benchmark_version"] for scenario in scenarios} != {manifest["benchmark_version"]}:
        raise ValidationError("review benchmark_version does not match scenario data")
    if {scenario["language"] for scenario in scenarios} != {manifest["language"]}:
        raise ValidationError("review language does not match scenario data")

    status_counts: Counter[str] = Counter()
    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        item = manifest["items"][scenario_id]
        if not isinstance(item, dict):
            raise ValidationError(f"review item {scenario_id} must be an object")
        expected_fields = {
            "concept_id",
            "context_id",
            "status",
            "reviewers",
            "reviewed_locales",
            "notes",
        }
        if set(item) != expected_fields:
            raise ValidationError(f"review item {scenario_id} has invalid fields")
        for field in ("concept_id", "context_id", "status", "notes"):
            if not isinstance(item[field], str):
                raise ValidationError(f"review item {scenario_id}.{field} must be a string")
        reviewers = _string_array(item["reviewers"], f"review item {scenario_id}.reviewers")
        locales = _string_array(
            item["reviewed_locales"],
            f"review item {scenario_id}.reviewed_locales",
        )
        status = item["status"]
        if status not in allowed_statuses:
            raise ValidationError(f"review item {scenario_id} has unknown status {status!r}")
        if status in REVIEWED_STATUSES and (len(reviewers) < 2 or not locales):
            raise ValidationError(
                f"review item {scenario_id} cannot claim {status!r} without "
                "two reviewers and at least one reviewed locale"
            )
        concept_tag = f"concept-{item['concept_id']}"
        context_tag = f"context-{item['context_id']}"
        if concept_tag not in scenario["tags"] or context_tag not in scenario["tags"]:
            raise ValidationError(f"review item {scenario_id} does not match scenario tags")
        status_counts[status] += 1

    return {
        "valid": True,
        "benchmark_version": manifest["benchmark_version"],
        "language": manifest["language"],
        "scenario_count": len(scenarios),
        "status_counts": dict(sorted(status_counts.items())),
        "culturally_reviewed_count": sum(
            count for status, count in status_counts.items() if status in REVIEWED_STATUSES
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate_review_manifest(args.scenarios, args.manifest)
    except ValidationError as exc:
        print(f"error: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
