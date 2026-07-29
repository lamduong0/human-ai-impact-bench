#!/usr/bin/env python3
"""Audit aligned EN/VI v0.6 concept pairs without claiming cultural validity."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import load_scenarios

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "scenario-coverage-standard.json"


def _load(source: Path) -> list[dict[str, Any]]:
    return [
        scenario for path in sorted(source.glob("*.jsonl")) for scenario in load_scenarios(path)
    ]


def _single_tag(scenario: dict[str, Any], prefix: str) -> str | None:
    values = [tag for tag in scenario["tags"] if tag.startswith(prefix)]
    return values[0] if len(values) == 1 else None


def build_report(
    en_source: Path,
    vi_source: Path,
    *,
    categories: set[str],
    expected_pairs_per_category: int,
) -> dict[str, Any]:
    en_scenarios = [scenario for scenario in _load(en_source) if scenario["category"] in categories]
    vi_scenarios = [scenario for scenario in _load(vi_source) if scenario["category"] in categories]
    issues: list[str] = []

    if {scenario["language"] for scenario in en_scenarios} - {"en"}:
        issues.append("English source contains a non-English record")
    if {scenario["language"] for scenario in vi_scenarios} - {"vi"}:
        issues.append("Vietnamese source contains a non-Vietnamese record")

    en_by_key = {
        (scenario["category"], scenario["scenario_id"]): scenario for scenario in en_scenarios
    }
    vi_by_key = {
        (scenario["category"], scenario["scenario_id"]): scenario for scenario in vi_scenarios
    }
    if len(en_by_key) != len(en_scenarios):
        issues.append("English bilingual track contains duplicate category/scenario identities")
    if len(vi_by_key) != len(vi_scenarios):
        issues.append("Vietnamese bilingual track contains duplicate category/scenario identities")

    en_counts = Counter(scenario["category"] for scenario in en_scenarios)
    vi_counts = Counter(scenario["category"] for scenario in vi_scenarios)
    for category in sorted(categories):
        if en_counts[category] != expected_pairs_per_category:
            issues.append(
                f"{category} has {en_counts[category]} English records; "
                f"expected {expected_pairs_per_category}"
            )
        if vi_counts[category] != expected_pairs_per_category:
            issues.append(
                f"{category} has {vi_counts[category]} Vietnamese records; "
                f"expected {expected_pairs_per_category}"
            )

    missing_vi = sorted(set(en_by_key) - set(vi_by_key))
    missing_en = sorted(set(vi_by_key) - set(en_by_key))
    if missing_vi:
        issues.append(f"{len(missing_vi)} pair(s) are missing Vietnamese members")
    if missing_en:
        issues.append(f"{len(missing_en)} pair(s) are missing English members")

    pair_violations: list[str] = []
    concept_counts: Counter[str] = Counter()
    context_tags: list[str] = []
    for key in sorted(set(en_by_key) & set(vi_by_key)):
        en = en_by_key[key]
        vi = vi_by_key[key]
        scenario_id = en["scenario_id"]
        for field in ("benchmark_version", "category", "risk_level", "dimensions"):
            if en[field] != vi[field]:
                pair_violations.append(f"{scenario_id} differs across languages on {field}")

        en_concept = _single_tag(en, "concept-")
        vi_concept = _single_tag(vi, "concept-")
        if en_concept is None or en_concept != vi_concept:
            pair_violations.append(f"{scenario_id} does not share exactly one concept tag")
        else:
            concept_counts[en_concept] += 1

        for language, scenario in (("en", en), ("vi", vi)):
            context_tag = _single_tag(scenario, "context-")
            if context_tag is None or not context_tag.endswith(f"-{language}"):
                pair_violations.append(
                    f"{scenario_id} {language} member has invalid language-specific context tag"
                )
            elif context_tag in context_tags:
                pair_violations.append(f"{context_tag} is reused")
            else:
                context_tags.append(context_tag)

        en_derivation = _single_tag(en, "derivation-")
        vi_derivation = _single_tag(vi, "derivation-")
        if en_derivation is None or en_derivation != vi_derivation:
            pair_violations.append(f"{scenario_id} has inconsistent derivation tags")
        elif en_derivation == "derivation-adapted":
            for prefix in ("source-version-", "source-scenario-"):
                if _single_tag(en, prefix) != _single_tag(vi, prefix):
                    pair_violations.append(
                        f"{scenario_id} adapted pair has inconsistent {prefix.rstrip('-')}"
                    )
        elif en_derivation == "derivation-authored-new":
            for scenario in (en, vi):
                if any(
                    tag.startswith(("source-version-", "source-scenario-"))
                    for tag in scenario["tags"]
                ):
                    pair_violations.append(f"{scenario_id} authored-new pair claims source lineage")
        else:
            pair_violations.append(f"{scenario_id} has unsupported derivation")

    invalid_concept_counts = {
        concept: count for concept, count in concept_counts.items() if count != 1
    }
    if invalid_concept_counts:
        issues.append(
            f"{len(invalid_concept_counts)} concept tag(s) do not identify one EN/VI pair"
        )
    if pair_violations:
        issues.append(f"{len(pair_violations)} bilingual pair invariant violation(s)")

    risk_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for category in sorted(categories):
        risk_counts[category] = dict(
            sorted(
                Counter(
                    scenario["risk_level"]
                    for scenario in en_scenarios
                    if scenario["category"] == category
                ).items()
            )
        )

    return {
        "valid": not issues,
        "audit_scope": "structural_bilingual_pair_alignment",
        "pair_count": len(set(en_by_key) & set(vi_by_key)),
        "physical_record_count": len(en_scenarios) + len(vi_scenarios),
        "category_counts": {
            category: {
                "en": en_counts[category],
                "vi": vi_counts[category],
            }
            for category in sorted(categories)
        },
        "risk_counts_by_category": dict(risk_counts),
        "pair_violations": pair_violations,
        "issues": issues,
        "limitations": [
            "Structural alignment does not establish translation quality or cultural validity.",
            "Qualified reviewers must assess meaning, naturalness, and locale-specific risk.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--en", type=Path, required=True)
    parser.add_argument("--vi", type=Path, required=True)
    parser.add_argument("--coverage-config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config = json.loads(args.coverage_config.read_text(encoding="utf-8"))["v0.6"]
    report = build_report(
        args.en,
        args.vi,
        categories=set(config["bilingual_categories"]),
        expected_pairs_per_category=config[
            "first_complete_checkpoint_records_per_language_in_bilingual_category"
        ],
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
