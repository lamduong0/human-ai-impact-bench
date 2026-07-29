#!/usr/bin/env python3
"""Find repeated long phrases that can reveal slot-filled scenario templates."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import load_scenarios

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_COMPONENTS = {
    "prompts": ("initial_prompt", "follow_up_prompts"),
    "expected_behaviors": ("expected_behaviors",),
    "failure_modes": ("failure_modes",),
}


def _load(source: Path) -> list[dict[str, Any]]:
    paths = sorted(source.glob("*.jsonl")) if source.is_dir() else [source]
    return [scenario for path in paths for scenario in load_scenarios(path)]


def _values(scenario: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for field in fields:
        value = scenario[field]
        values.extend(value if isinstance(value, list) else [value])
    return values


def _ngrams(value: str, size: int) -> set[tuple[str, ...]]:
    tokens = _TOKEN_PATTERN.findall(value.casefold())
    return {tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def build_report(
    source: Path,
    *,
    ngram_size: int = 7,
    minimum_scenarios: int = 3,
    categories: set[str] | None = None,
) -> dict[str, Any]:
    scenarios = [
        scenario
        for scenario in _load(source)
        if "derivation-authored-new" in scenario["tags"]
        and (categories is None or scenario["category"] in categories)
    ]
    groups: dict[
        tuple[str, str, str, tuple[str, ...]],
        set[str],
    ] = defaultdict(set)
    for scenario in scenarios:
        for component, fields in _COMPONENTS.items():
            for value in _values(scenario, fields):
                for ngram in _ngrams(value, ngram_size):
                    groups[
                        (
                            scenario["language"],
                            scenario["category"],
                            component,
                            ngram,
                        )
                    ].add(scenario["scenario_id"])

    candidates = [
        {
            "language": language,
            "category": category,
            "component": component,
            "phrase": " ".join(ngram),
            "scenario_count": len(scenario_ids),
            "scenario_ids": sorted(scenario_ids),
        }
        for (language, category, component, ngram), scenario_ids in groups.items()
        if len(scenario_ids) >= minimum_scenarios
    ]
    candidates.sort(
        key=lambda item: (
            -item["scenario_count"],
            item["language"],
            item["category"],
            item["component"],
            item["phrase"],
        )
    )
    return {
        "audit_version": "0.1",
        "audit_scope": "authored_new_repeated_phrase_candidates",
        "source": str(source),
        "authored_new_scenario_count": len(scenarios),
        "ngram_size": ngram_size,
        "minimum_scenarios": minimum_scenarios,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "limitations": [
            "Repeated phrases are template-review candidates, not automatic defects.",
            "The audit does not detect paraphrased templates or semantic duplicates.",
            "Adapted source records are excluded because their wording is immutable.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--ngram-size", type=int, default=7)
    parser.add_argument("--minimum-scenarios", type=int, default=3)
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.ngram_size < 2:
        parser.error("--ngram-size must be at least 2")
    if args.minimum_scenarios < 2:
        parser.error("--minimum-scenarios must be at least 2")

    report = build_report(
        args.source,
        ngram_size=args.ngram_size,
        minimum_scenarios=args.minimum_scenarios,
        categories=set(args.category) or None,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
