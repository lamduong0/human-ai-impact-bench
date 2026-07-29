"""Measure how much independent evidence a scenario set actually carries.

Template-derived corpora expand a small number of concepts across many
contexts. The resulting records have distinct ``scenario_id`` values, so record
count overstates independent evidence: sibling records share a concept, a
follow-up template, and a judge rubric, and their scores move together.

``cluster_diagnostics`` reports the one-way ICC of per-scenario scores within a
cluster key, the resulting design effect, and the effective sample size.
Interpret a benchmark comparison against ``effective_records``, not
``scenario_records``.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

from humanai_impact_bench.deployment import load_scenario_source
from humanai_impact_bench.validation import ValidationError

_TOOL_NAME = "HumanAI-Impact-Bench"


def _cluster_key(scenario: dict[str, Any], prefix: str) -> str:
    values = [tag for tag in scenario["tags"] if tag.startswith(prefix)]
    if len(values) != 1:
        raise ValidationError(
            f"scenario {scenario['scenario_id']} does not carry exactly one {prefix!r} tag; "
            "use a different cluster tag prefix"
        )
    return values[0]


def _one_way_icc(groups: list[list[float]]) -> tuple[float, float]:
    """Return (ICC, mean cluster size) for a one-way random-effects model.

    Clusters of unequal size use the standard ``n0`` correction so an
    unbalanced corpus does not silently inflate the estimate.
    """
    sizes = [len(group) for group in groups]
    total = sum(sizes)
    cluster_count = len(groups)
    if cluster_count < 2 or total <= cluster_count:
        return 0.0, float(total) / max(cluster_count, 1)
    grand_mean = fmean(value for group in groups for value in group)
    between = sum(len(group) * (fmean(group) - grand_mean) ** 2 for group in groups) / (
        cluster_count - 1
    )
    within = sum(sum((value - fmean(group)) ** 2 for value in group) for group in groups) / (
        total - cluster_count
    )
    n0 = (total - sum(size**2 for size in sizes) / total) / (cluster_count - 1)
    denominator = between + (n0 - 1) * within
    if denominator <= 0:
        return 0.0, n0
    return (between - within) / denominator, n0


def cluster_diagnostics(
    *,
    report_path: str | Path,
    scenarios_path: str | Path,
    cluster_tag_prefix: str = "concept-",
) -> dict[str, Any]:
    """Report cluster correlation and effective sample size for one report."""
    source = Path(report_path)
    try:
        report = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {source}") from exc
    except OSError as exc:
        raise ValidationError(f"could not read {source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{source}: invalid JSON: {exc.msg}") from exc
    if not isinstance(report, dict):
        raise ValidationError("report must be a JSON object")

    scenario_results = report.get("scenario_results")
    if not isinstance(scenario_results, dict) or not scenario_results:
        raise ValidationError(f"{source}: report has no scenario_results to analyze")

    scenarios, _digest = load_scenario_source(scenarios_path)
    cluster_by_identity = {
        f"{scenario['scenario_id']}:{scenario['language']}": _cluster_key(
            scenario, cluster_tag_prefix
        )
        for scenario in scenarios
    }
    missing = sorted(set(scenario_results) - set(cluster_by_identity))
    if missing:
        raise ValidationError(
            "report scenario_results not present in the scenario source: " + ", ".join(missing)
        )

    grouped: dict[str, list[float]] = defaultdict(list)
    for identity, result in scenario_results.items():
        if not isinstance(result, dict) or "overall_score" not in result:
            raise ValidationError(f"report scenario_results.{identity} missing overall_score")
        value = result["overall_score"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(
                f"report scenario_results.{identity}.overall_score must be a number"
            )
        score = float(value)
        if not math.isfinite(score) or not 0 <= score <= 100:
            raise ValidationError(
                f"report scenario_results.{identity}.overall_score must be between 0 and 100"
            )
        grouped[cluster_by_identity[identity]].append(score)

    groups = [grouped[key] for key in sorted(grouped)]
    icc, mean_cluster_size = _one_way_icc(groups)
    design_effect = 1 + (mean_cluster_size - 1) * max(icc, 0.0)
    record_count = sum(len(group) for group in groups)
    return {
        "tool": _TOOL_NAME,
        "analysis": "cluster_diagnostics",
        "model": report.get("model"),
        "report": str(source),
        "scenarios": str(scenarios_path),
        "cluster_tag_prefix": cluster_tag_prefix,
        "scenario_records": record_count,
        "clusters": len(groups),
        "mean_cluster_size": round(mean_cluster_size, 3),
        "intraclass_correlation": round(icc, 3),
        "design_effect": round(design_effect, 2),
        "effective_records": round(record_count / design_effect, 1),
        "note": (
            "effective_records is the independent-evidence equivalent of "
            "scenario_records. Score differences between candidates must be "
            "interpreted against effective_records."
        ),
    }
