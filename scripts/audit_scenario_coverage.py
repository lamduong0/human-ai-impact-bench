#!/usr/bin/env python3
"""Run deterministic exact coverage checks without treating matched twins as duplicates."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import load_scenarios


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _prompt_signature(scenario: dict[str, Any]) -> str:
    prompts = [scenario["initial_prompt"], *scenario["follow_up_prompts"]]
    return "\x1f".join(_normalize(prompt) for prompt in prompts)


def _sequence_signature(values: list[str]) -> str:
    return "\x1f".join(_normalize(value) for value in values)


def _duplicate_groups(
    scenarios: list[dict[str, Any]],
    signature,
    *,
    matched: bool,
) -> list[list[str]]:
    signature_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for scenario in scenarios:
        signature_groups[signature(scenario)].append(scenario)

    groups: list[list[str]] = []
    for members in signature_groups.values():
        pair_ids = {member.get("matched_pair_id") for member in members}
        if len(members) > 1 and (not matched or len(pair_ids) != 1):
            groups.append(sorted(member["scenario_id"] for member in members))
    return sorted(groups)


def _repeated_list_item_groups(
    scenarios: list[dict[str, Any]],
    field: str,
    *,
    matched: bool,
) -> list[list[str]]:
    item_groups: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for scenario in scenarios:
        for value in scenario[field]:
            item_groups[_normalize(value)][scenario["scenario_id"]] = scenario

    groups: list[list[str]] = []
    for members_by_id in item_groups.values():
        members = list(members_by_id.values())
        pair_ids = {member.get("matched_pair_id") for member in members}
        if len(members) > 1 and (not matched or len(pair_ids) != 1):
            groups.append(sorted(members_by_id))
    return sorted(groups)


def _tag_value(scenario: dict[str, Any], prefix: str) -> str | None:
    values = [tag for tag in scenario["tags"] if tag.startswith(prefix)]
    return values[0] if len(values) == 1 else None


def _load_source(source: Path) -> list[dict[str, Any]]:
    paths = sorted(source.rglob("*.jsonl")) if source.is_dir() else [source]
    return [scenario for path in paths for scenario in load_scenarios(path)]


def build_report(
    source: Path,
    *,
    expected_per_category: int | None = None,
    expected_categories: set[str] | None = None,
    matched: bool = False,
    selection_identities: set[tuple[str, str]] | None = None,
    strict_list_items: bool = False,
) -> dict[str, Any]:
    scenarios = _load_source(source)
    if selection_identities is not None:
        scenarios = [
            scenario
            for scenario in scenarios
            if (scenario["language"], scenario["scenario_id"]) in selection_identities
        ]
        actual_identities = {
            (scenario["language"], scenario["scenario_id"]) for scenario in scenarios
        }
        if actual_identities != selection_identities:
            missing = sorted(selection_identities - actual_identities)
            raise ValueError(f"coverage selection contains missing identities: {missing}")
    issues: list[str] = []
    category_counts = Counter(scenario["category"] for scenario in scenarios)

    if not scenarios:
        issues.append("scenario source is empty")
    if expected_categories is not None:
        actual_categories = set(category_counts)
        missing_categories = sorted(expected_categories - actual_categories)
        extra_categories = sorted(actual_categories - expected_categories)
        if missing_categories:
            issues.append(f"missing categories: {', '.join(missing_categories)}")
        if extra_categories:
            issues.append(f"unexpected categories: {', '.join(extra_categories)}")

    if expected_per_category is not None:
        for category, count in sorted(category_counts.items()):
            if count != expected_per_category:
                issues.append(f"{category} has {count} records; expected {expected_per_category}")

    scenario_identities = [
        (scenario["language"], scenario["scenario_id"]) for scenario in scenarios
    ]
    duplicate_identities = sorted(
        identity for identity, count in Counter(scenario_identities).items() if count > 1
    )
    if duplicate_identities:
        rendered = ", ".join(
            f"{language}:{scenario_id}" for language, scenario_id in duplicate_identities
        )
        issues.append(f"duplicate language/scenario identities: {rendered}")

    duplicate_prompt_groups = _duplicate_groups(
        scenarios,
        _prompt_signature,
        matched=matched,
    )
    if duplicate_prompt_groups:
        issues.append(
            f"{len(duplicate_prompt_groups)} exact prompt sequence(s) repeat across constructs"
        )

    repeated_component_groups = {
        "context": _duplicate_groups(
            scenarios,
            lambda scenario: _normalize(scenario["context"]),
            matched=matched,
        ),
        "follow_up_prompts": _duplicate_groups(
            scenarios,
            lambda scenario: _sequence_signature(scenario["follow_up_prompts"]),
            matched=matched,
        ),
        "expected_behaviors": _duplicate_groups(
            scenarios,
            lambda scenario: _sequence_signature(scenario["expected_behaviors"]),
            matched=matched,
        ),
        "failure_modes": _duplicate_groups(
            scenarios,
            lambda scenario: _sequence_signature(scenario["failure_modes"]),
            matched=matched,
        ),
        "follow_up_prompt_items": _repeated_list_item_groups(
            scenarios,
            "follow_up_prompts",
            matched=matched,
        ),
        "expected_behavior_items": _repeated_list_item_groups(
            scenarios,
            "expected_behaviors",
            matched=matched,
        ),
        "failure_mode_items": _repeated_list_item_groups(
            scenarios,
            "failure_modes",
            matched=matched,
        ),
    }
    for component, groups in repeated_component_groups.items():
        is_item_level = component.endswith("_items")
        if groups and (strict_list_items or not is_item_level):
            issues.append(f"{len(groups)} exact {component} value(s) repeat across constructs")

    pair_violations: list[str] = []
    if matched:
        by_pair: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
        for scenario in scenarios:
            by_pair[scenario.get("matched_pair_id")].append(scenario)
        if None in by_pair:
            pair_violations.append("records are missing matched_pair_id")
        for pair_id, members in sorted(
            ((key, value) for key, value in by_pair.items() if key is not None)
        ):
            modes = {member.get("protocol_mode") for member in members}
            signatures = {_prompt_signature(member) for member in members}
            pair_concept_tags = {_tag_value(member, "concept-") for member in members}
            invariant_fields = (
                "category",
                "language",
                "locale",
                "risk_level",
                "dimensions",
                "initial_prompt",
                "follow_up_prompts",
            )
            divergent_fields = [
                field
                for field in invariant_fields
                if len(
                    {
                        json.dumps(
                            member.get(field),
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        for member in members
                    }
                )
                != 1
            ]
            if len({member.get("persona", {}).get("age_group") for member in members}) != 1:
                divergent_fields.append("persona.age_group")
            if len(members) != 2:
                pair_violations.append(f"{pair_id} has {len(members)} members")
            elif modes != {"continuous", "prefill_recovery"}:
                pair_violations.append(f"{pair_id} has invalid protocol modes")
            elif len(signatures) != 1:
                pair_violations.append(f"{pair_id} does not preserve its prompt sequence")
            elif divergent_fields:
                pair_violations.append(
                    f"{pair_id} diverges on invariant fields: {', '.join(divergent_fields)}"
                )
            elif len(pair_concept_tags) != 1 or None in pair_concept_tags:
                pair_violations.append(f"{pair_id} does not preserve one concept tag")
        if pair_violations:
            issues.append(f"{len(pair_violations)} matched-pair violation(s)")

    concept_counts = Counter(
        value for scenario in scenarios if (value := _tag_value(scenario, "concept-")) is not None
    )
    missing_concept_tags = [
        scenario["scenario_id"]
        for scenario in scenarios
        if _tag_value(scenario, "concept-") is None
    ]
    if missing_concept_tags:
        issues.append(f"{len(missing_concept_tags)} invalid concept tag assignment(s)")
    if matched:
        invalid_concept_counts = {
            concept: count for concept, count in concept_counts.items() if count != 2
        }
        if invalid_concept_counts:
            issues.append(f"{len(invalid_concept_counts)} concept tag(s) do not identify one pair")

    context_tags = [
        value for scenario in scenarios if (value := _tag_value(scenario, "context-")) is not None
    ]
    if len(context_tags) != len(scenarios):
        issues.append("one or more records have an invalid context tag assignment")
    duplicate_context_tags = sorted(
        tag for tag, count in Counter(context_tags).items() if count > 1
    )
    if duplicate_context_tags:
        issues.append(f"{len(duplicate_context_tags)} context tag(s) are reused")

    def nested_counts(field: str) -> dict[str, dict[str, int]]:
        return {
            category: dict(
                sorted(
                    Counter(
                        scenario[field]
                        for scenario in scenarios
                        if scenario["category"] == category and field in scenario
                    ).items()
                )
            )
            for category in sorted(category_counts)
        }

    return {
        "valid": not issues,
        "audit_scope": "deterministic_exact",
        "source": str(source.resolve()),
        "scenario_count": len(scenarios),
        "category_counts": dict(sorted(category_counts.items())),
        "language_counts_by_category": nested_counts("language"),
        "locale_counts_by_category": nested_counts("locale"),
        "risk_counts_by_category": nested_counts("risk_level"),
        "protocol_counts_by_category": nested_counts("protocol_mode"),
        "duplicate_prompt_groups": sorted(duplicate_prompt_groups),
        "repeated_component_groups": repeated_component_groups,
        "pair_violations": pair_violations,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--expected-per-category", type=int)
    parser.add_argument("--coverage-config", type=Path)
    parser.add_argument("--track")
    parser.add_argument("--matched", action="store_true")
    parser.add_argument(
        "--strict-list-items",
        action="store_true",
        help="Fail on repeated individual prompt, behavior, or failure-mode items.",
    )
    parser.add_argument(
        "--selection",
        type=Path,
        help="Optional JSON selection with items containing language and scenario_id.",
    )
    args = parser.parse_args()

    expected_categories = None
    expected_per_category = args.expected_per_category
    if args.coverage_config:
        if not args.track:
            parser.error("--track is required with --coverage-config")
        config = json.loads(args.coverage_config.read_text(encoding="utf-8"))
        try:
            track = config[args.track]
            expected_categories = set(track.get("current_stage_categories", track["categories"]))
            configured_checkpoint = track.get("current_stage_records_per_category")
            if configured_checkpoint is None:
                configured_checkpoint = track["active_checkpoint_records_per_category"]
        except (KeyError, TypeError) as exc:
            parser.error(f"coverage config does not define track {args.track!r}: {exc}")
        if expected_per_category is None:
            expected_per_category = configured_checkpoint
        elif expected_per_category != configured_checkpoint:
            parser.error("--expected-per-category conflicts with the configured active checkpoint")

    selection_identities = None
    if args.selection:
        selection = json.loads(args.selection.read_text(encoding="utf-8"))
        selection_identities = {
            (item["language"], item["scenario_id"]) for item in selection["items"]
        }
    report = build_report(
        args.source,
        expected_per_category=expected_per_category,
        expected_categories=expected_categories,
        matched=args.matched,
        selection_identities=selection_identities,
        strict_list_items=args.strict_list_items,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
