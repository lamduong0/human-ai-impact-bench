#!/usr/bin/env python3
"""Report lexical near-duplicate candidates for human construct review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import load_scenarios

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
ROOT = Path(__file__).resolve().parents[1]


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def _load(source: Path) -> list[dict[str, Any]]:
    paths = sorted(source.rglob("*.jsonl")) if source.is_dir() else [source]
    return [scenario for path in paths for scenario in load_scenarios(path)]


def _prompt_text(scenario: dict[str, Any]) -> str:
    return " ".join([scenario["initial_prompt"], *scenario["follow_up_prompts"]]).casefold()


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(text))


def _is_authored_new(scenario: dict[str, Any]) -> bool:
    return "derivation-authored-new" in scenario["tags"]


def scenario_set_digest(scenarios: list[dict[str, Any]]) -> str:
    ordered = sorted(
        scenarios,
        key=lambda scenario: (
            scenario["benchmark_version"],
            scenario["language"],
            scenario["scenario_id"],
        ),
    )
    payload = json.dumps(
        ordered,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _pair_result(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    sequence_threshold: float,
    jaccard_threshold: float,
    scope: str,
) -> dict[str, Any] | None:
    left_text = _prompt_text(left)
    right_text = _prompt_text(right)
    left_tokens = _tokens(left_text)
    right_tokens = _tokens(right_text)
    token_union = left_tokens | right_tokens
    token_jaccard = len(left_tokens & right_tokens) / len(token_union) if token_union else 1.0
    matcher = SequenceMatcher(None, left_text, right_text)
    if token_jaccard < jaccard_threshold and (
        matcher.real_quick_ratio() < sequence_threshold
        or matcher.quick_ratio() < sequence_threshold
    ):
        return None
    sequence_ratio = matcher.ratio()
    if sequence_ratio < sequence_threshold and token_jaccard < jaccard_threshold:
        return None
    return {
        "scope": scope,
        "left_scenario_id": left["scenario_id"],
        "left_category": left["category"],
        "left_version": left["benchmark_version"],
        "right_scenario_id": right["scenario_id"],
        "right_category": right["category"],
        "right_version": right["benchmark_version"],
        "sequence_ratio": round(sequence_ratio, 4),
        "token_jaccard": round(token_jaccard, 4),
    }


def build_report(
    source: Path,
    *,
    compare_sources: list[Path] | None = None,
    sequence_threshold: float = 0.58,
    jaccard_threshold: float = 0.45,
    selection_identities: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    scenarios = _load(source)
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
            raise ValueError(f"similarity selection contains missing identities: {missing}")
    candidates: list[dict[str, Any]] = []
    for index, left in enumerate(scenarios):
        for right in scenarios[index + 1 :]:
            candidate = _pair_result(
                left,
                right,
                sequence_threshold=sequence_threshold,
                jaccard_threshold=jaccard_threshold,
                scope="within_source",
            )
            if candidate is not None:
                candidates.append(candidate)

    historical = [
        scenario for compare_source in compare_sources or [] for scenario in _load(compare_source)
    ]
    authored_new = [scenario for scenario in scenarios if _is_authored_new(scenario)]
    for left in authored_new:
        for right in historical:
            candidate = _pair_result(
                left,
                right,
                sequence_threshold=sequence_threshold,
                jaccard_threshold=jaccard_threshold,
                scope="authored_new_vs_history",
            )
            if candidate is not None:
                candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            -max(item["sequence_ratio"], item["token_jaccard"]),
            item["scope"],
            item["left_scenario_id"],
            item["right_scenario_id"],
        )
    )
    return {
        "audit_version": "0.1",
        "audit_scope": "lexical_candidate_generation",
        "source": _display_path(source),
        "source_scenario_sha256": scenario_set_digest(scenarios),
        "comparison_sources": [
            _display_path(compare_source) for compare_source in compare_sources or []
        ],
        "comparison_scenario_sha256": scenario_set_digest(historical),
        "scenario_count": len(scenarios),
        "authored_new_count": len(authored_new),
        "historical_scenario_count": len(historical),
        "selection_identity_count": (
            len(selection_identities) if selection_identities is not None else None
        ),
        "sequence_threshold": sequence_threshold,
        "token_jaccard_threshold": jaccard_threshold,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "limitations": [
            "A lexical match is a review candidate, not proof of construct duplication.",
            "No lexical match is not proof of semantic independence.",
            "Adapted records are excluded from historical comparison because their exact "
            "source relationship is already recorded in the lineage index.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--compare", type=Path, action="append", default=[])
    parser.add_argument("--sequence-threshold", type=float, default=0.58)
    parser.add_argument("--jaccard-threshold", type=float, default=0.45)
    parser.add_argument(
        "--selection",
        type=Path,
        help="Optional JSON selection with items containing language and scenario_id.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--fail-on-candidates",
        action="store_true",
        help="Exit 1 when lexical review candidates are present.",
    )
    args = parser.parse_args()

    selection_identities = None
    if args.selection:
        selection = json.loads(args.selection.read_text(encoding="utf-8"))
        selection_identities = {
            (item["language"], item["scenario_id"]) for item in selection["items"]
        }
    report = build_report(
        args.source,
        compare_sources=args.compare,
        sequence_threshold=args.sequence_threshold,
        jaccard_threshold=args.jaccard_threshold,
        selection_identities=selection_identities,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if args.fail_on_candidates and report["candidate_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
