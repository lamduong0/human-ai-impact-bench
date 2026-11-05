"""Matched, descriptive diagnostics for automated v0.8 evaluations.

Judges remain separate instruments. Repeated ratings and synthetic expectations
are never represented as independent scenarios or human ground truth.
"""

from __future__ import annotations

import json
import math
import os
import random
import tempfile
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from statistics import fmean
from typing import Any

from humanai_impact_bench.constants import CRITICAL_FAILURE_PENALTIES, DIMENSION_WEIGHTS
from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.scoring import score_annotations
from humanai_impact_bench.validation import ValidationError

_SEED = 20261105
_RESAMPLES = 2000


def agreement_metrics(left: list[int], right: list[int]) -> dict[str, Any]:
    """Return raw ordinal agreement and quadratic weighted Cohen's kappa."""
    if len(left) != len(right):
        raise ValidationError("agreement vectors must have equal lengths")
    for value in [*left, *right]:
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise ValidationError("agreement requires integer scores from 1 to 5")
    n = len(left)
    result: dict[str, Any] = {
        "n": n,
        "exact_agreement": None,
        "mean_absolute_difference": None,
        "quadratic_weighted_kappa": None,
        "degenerate_distribution": len(set(left)) < 2 or len(set(right)) < 2,
        "reason": "no_matched_observations" if not n else None,
    }
    if not n:
        return result
    result["exact_agreement"] = sum(a == b for a, b in zip(left, right, strict=True)) / n
    result["mean_absolute_difference"] = fmean(abs(a - b) for a, b in zip(left, right, strict=True))
    first, second = Counter(left), Counter(right)
    expected = sum(
        (a - b) ** 2 * na * nb / n**2 for a, na in first.items() for b, nb in second.items()
    )
    if expected > 0:
        observed = fmean((a - b) ** 2 for a, b in zip(left, right, strict=True))
        result["quadratic_weighted_kappa"] = 1 - observed / expected
    else:
        result["reason"] = "degenerate_distribution"
    return result


def _validate_groups(values: dict[str, list[float]]) -> None:
    if not isinstance(values, dict):
        raise ValidationError("family values must be a mapping")
    for family, items in values.items():
        if not isinstance(family, str) or not family or not isinstance(items, list) or not items:
            raise ValidationError("each family needs an identity and nonempty observations")
        if any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in items
        ):
            raise ValidationError("family observations must be finite numbers")


def _percentile(values: list[float], fraction: float) -> float:
    position = (len(values) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def _interval(
    groups: dict[str, dict[str, list[float]]], *, seed: int, resamples: int, pooled: bool
) -> dict[str, Any]:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValidationError("bootstrap seed must be an integer")
    if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples < 2:
        raise ValidationError("bootstrap requires at least two resamples")
    for families in groups.values():
        _validate_groups(families)
    family_count = sum(len(families) for families in groups.values())
    observations = sum(len(v) for families in groups.values() for v in families.values())
    result: dict[str, Any] = {
        "method": "category_stratified_family_bootstrap" if pooled else "family_bootstrap",
        "families": family_count,
        "observations": observations,
        "seed": seed,
        "resamples": resamples,
        "lower": None,
        "upper": None,
        "reason": None,
        "estimand": "mean_per_rating_scenario_score",
    }
    if family_count < 5 or (pooled and any(len(v) < 2 for v in groups.values())):
        result["reason"] = "insufficient_family_support"
        return result
    rng = random.Random(seed)
    weights = {
        category: sum(len(v) for v in families.values()) / observations
        for category, families in groups.items()
    }
    draws = []
    for _ in range(resamples):
        estimate = 0.0
        for category, families in sorted(groups.items()):
            names = sorted(families)
            sampled = [rng.choice(names) for _ in names]
            estimate += weights[category] * fmean(
                value for name in sampled for value in families[name]
            )
        draws.append(estimate)
    draws.sort()
    result["lower"] = _percentile(draws, 0.025)
    result["upper"] = _percentile(draws, 0.975)
    return result


def family_interval(
    values: dict[str, list[float]], *, seed: int = _SEED, resamples: int = _RESAMPLES
) -> dict[str, Any]:
    """Bootstrap whole families in one category; decline thin strata."""
    return _interval({"single": values}, seed=seed, resamples=resamples, pooled=False)


def _transcript_key(row: dict[str, Any]) -> tuple:
    return (
        row["scenario_id"],
        row["scenario_digest"],
        row["target_id"],
        row["generation_replicate"],
        row["fixture_id"],
        row["transcript_digest"],
    )


def _validate_rows(rows: list[dict[str, Any]]) -> None:
    seen: set[tuple] = set()
    fixed_transcripts: dict[tuple, str] = {}
    metadata: dict[str, tuple] = {}
    for row in rows:
        if row["kind"] not in {"rating", "fixture_rating"}:
            raise ValidationError("report rows must be candidate or fixture ratings")
        if row["track"] not in {"core", "agentic"} or row["split"] not in {
            "calibration",
            "public_evaluation",
        }:
            raise ValidationError("report row has an unsupported track or split")
        if row["kind"] == "fixture_rating" and row["split"] != "calibration":
            raise ValidationError("synthetic fixtures must be calibration-only")
        identity = (
            row["kind"],
            row["scenario_id"],
            row["target_id"],
            row["generation_replicate"],
            row["judge_id"],
            row["rating_replicate"],
            row["fixture_id"],
        )
        if identity in seen:
            raise ValidationError("duplicate rating identity in study report")
        seen.add(identity)
        source = (
            row["scenario_digest"],
            row["track"],
            row["split"],
            row["category"],
            row["family_id"],
            row["context_id"],
            row["matched_pair_id"],
            row["protocol_mode"],
        )
        prior = metadata.setdefault(row["scenario_id"], source)
        if prior != source:
            raise ValidationError("scenario metadata differs between ratings")
        fixed = (
            row["scenario_id"],
            row["target_id"],
            row["generation_replicate"],
            row["fixture_id"],
        )
        if (
            fixed_transcripts.setdefault(fixed, row["transcript_digest"])
            != row["transcript_digest"]
        ):
            raise ValidationError("fixed transcript differs between judges or rating replicates")
        scores = row["scores"]
        if not isinstance(scores, dict) or not scores or set(scores) - set(DIMENSION_WEIGHTS):
            raise ValidationError("report scores must use known dimensions")
        agreement_metrics(list(scores.values()), list(scores.values()))
        failures = row["critical_failures"]
        if not isinstance(failures, list) or len(set(failures)) != len(failures):
            raise ValidationError("critical failures must be a unique list")
        if set(failures) - set(CRITICAL_FAILURE_PENALTIES):
            raise ValidationError("unknown critical failure label")


def _score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    annotations = [
        {
            "benchmark_version": "0.8",
            "benchmark_track": r["track"],
            "language": "en",
            "scenario_id": r["scenario_id"],
            "model": r["target_id"] or "synthetic_authored",
            "rater_id": r["task_id"],
            "scores": r["scores"],
            "critical_failures": r["critical_failures"],
        }
        for r in rows
    ]
    return score_annotations(annotations)[0].to_dict()


def _critical_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    transcripts = {_transcript_key(r) for r in rows}
    affected = {_transcript_key(r) for r in rows if r["critical_failures"]}
    labels = {}
    for label in CRITICAL_FAILURE_PENALTIES:
        events = [r for r in rows if label in r["critical_failures"]]
        unique = {_transcript_key(r) for r in events}
        labels[label] = {
            "rating_events": len(events),
            "rating_denominator": len(rows),
            "rating_prevalence": len(events) / len(rows) if rows else None,
            "unique_affected_transcripts": len(unique),
            "transcript_denominator": len(transcripts),
            "any_rating_labelled_prevalence": len(unique) / len(transcripts)
            if transcripts
            else None,
        }
    return {
        "unique_affected_transcripts": len(affected),
        "transcript_denominator": len(transcripts),
        "labels": labels,
    }


def _summarize(
    rows: list[dict[str, Any]], *, pooled: bool, seed: int, resamples: int
) -> dict[str, Any]:
    strata: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        strata[row["category"]][row["family_id"]].append(_score([row])["overall_score"])
    return {
        "rating_count": len(rows),
        "transcript_count": len({_transcript_key(r) for r in rows}),
        "scenario_count": len({r["scenario_id"] for r in rows}),
        "family_count": len({(r["category"], r["family_id"]) for r in rows}),
        "pair_count": len({r["matched_pair_id"] for r in rows if r["matched_pair_id"]}),
        "scores": _score(rows),
        "critical_failures": _critical_summary(rows),
        "interval": _interval(dict(strata), seed=seed, resamples=resamples, pooled=pooled),
    }


def _candidate_results(
    rows: list[dict[str, Any]], *, seed: int, resamples: int
) -> list[dict[str, Any]]:
    groups: dict[tuple, list] = defaultdict(list)
    for row in rows:
        if row["kind"] == "rating":
            groups[(row["track"], row["split"], row["target_id"], row["judge_id"])].append(row)
    results = []
    for (track, split, target, judge), group in sorted(groups.items()):
        categories: dict[str, list] = defaultdict(list)
        for row in group:
            categories[row["category"]].append(row)
        results.append(
            {
                "track": track,
                "split": split,
                "target_id": target,
                "judge_id": judge,
                **_summarize(group, pooled=True, seed=seed, resamples=resamples),
                "categories": {
                    k: _summarize(v, pooled=False, seed=seed, resamples=resamples)
                    for k, v in sorted(categories.items())
                },
            }
        )
    return results


def _candidate_contrasts(rows: list[dict], *, seed: int, resamples: int) -> list[dict]:
    groups: dict[tuple, dict[str, dict[tuple, dict]]] = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        if row["kind"] == "rating":
            group = (row["track"], row["split"], row["judge_id"])
            key = (row["scenario_id"], row["generation_replicate"], row["rating_replicate"])
            groups[group][row["target_id"]][key] = row
    results = []
    for (track, split, judge), candidates in sorted(groups.items()):
        for first, second in combinations(sorted(candidates), 2):
            left, right = candidates[first], candidates[second]
            shared = sorted(set(left) & set(right))
            strata: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
            dimension_differences: dict[str, list] = defaultdict(list)
            deltas = []
            for key in shared:
                a, b = left[key], right[key]
                delta = _score([b])["overall_score"] - _score([a])["overall_score"]
                deltas.append(delta)
                strata[a["category"]][a["family_id"]].append(delta)
                for dimension in set(a["scores"]) & set(b["scores"]):
                    dimension_differences[dimension].append(
                        b["scores"][dimension] - a["scores"][dimension]
                    )
            interval = _interval(dict(strata), seed=seed, resamples=resamples, pooled=True)
            interval["estimand"] = "mean_matched_scenario_score_difference"
            results.append(
                {
                    "track": track,
                    "split": split,
                    "judge_id": judge,
                    "left_target_id": first,
                    "right_target_id": second,
                    "direction": "right_minus_left",
                    "matched_ratings": len(shared),
                    "matched_scenarios": len({key[0] for key in shared}),
                    "unmatched_left": len(left) - len(shared),
                    "unmatched_right": len(right) - len(shared),
                    "mean_overall_score_difference": fmean(deltas) if deltas else None,
                    "dimension_differences": {
                        dimension: {"n": len(values), "mean": fmean(values)}
                        for dimension, values in sorted(dimension_differences.items())
                    },
                    "interval": interval,
                }
            )
    return results


def _binary_agreement(pairs: list[tuple[dict, dict]], label: str) -> dict[str, Any]:
    cells = {"both_absent": 0, "left_only": 0, "right_only": 0, "both_present": 0}
    for left, right in pairs:
        a, b = label in left["critical_failures"], label in right["critical_failures"]
        key = (
            "both_present"
            if a and b
            else "left_only"
            if a
            else "right_only"
            if b
            else "both_absent"
        )
        cells[key] += 1
    n = len(pairs)
    left_rate = (cells["left_only"] + cells["both_present"]) / n if n else None
    right_rate = (cells["right_only"] + cells["both_present"]) / n if n else None
    exact = (cells["both_absent"] + cells["both_present"]) / n if n else None
    chance = left_rate * right_rate + (1 - left_rate) * (1 - right_rate) if n else None
    kappa = (exact - chance) / (1 - chance) if n and chance < 1 else None
    return {
        **cells,
        "n": n,
        "left_prevalence": left_rate,
        "right_prevalence": right_rate,
        "exact_agreement": exact,
        "kappa": kappa,
        "degenerate_distribution": left_rate in {0, 1} or right_rate in {0, 1},
        "reason": None if kappa is not None else "degenerate_distribution" if n else "no_pairs",
    }


def _agreement_summary(left: list[dict], right: list[dict], *, align_replicate: bool) -> dict:
    def index(items):
        return {
            (*_transcript_key(r), r["rating_replicate"] if align_replicate else None): r
            for r in items
        }

    first, second = index(left), index(right)
    shared = sorted(set(first) & set(second), key=repr)
    pairs = [(first[k], second[k]) for k in shared]
    dimensions = {}
    for dimension in DIMENSION_WEIGHTS:
        applicable = [
            (a["scores"][dimension], b["scores"][dimension])
            for a, b in pairs
            if dimension in a["scores"] and dimension in b["scores"]
        ]
        if applicable:
            dimensions[dimension] = agreement_metrics(
                [p[0] for p in applicable], [p[1] for p in applicable]
            )
    return {
        "matched_transcripts": len({_transcript_key(a) for a, _ in pairs}),
        "matched_ratings": len(pairs),
        "unmatched_left": len(first) - len(pairs),
        "unmatched_right": len(second) - len(pairs),
        "dimensions": dimensions,
        "critical_failures": {
            label: _binary_agreement(pairs, label) for label in CRITICAL_FAILURE_PENALTIES
        },
    }


def _agreements(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    groups: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        groups[(row["track"], row["split"], row["kind"], row["target_id"])][row["judge_id"]].append(
            row
        )
    within, between = [], []
    for key, judges in sorted(groups.items(), key=lambda item: repr(item[0])):
        metadata = dict(zip(("track", "split", "kind", "target_id"), key, strict=True))
        for judge, judged in sorted(judges.items()):
            repeats: dict[int, list] = defaultdict(list)
            for row in judged:
                repeats[row["rating_replicate"]].append(row)
            for left, right in combinations(sorted(repeats), 2):
                within.append(
                    {
                        **metadata,
                        "judge_id": judge,
                        "left_replicate": left,
                        "right_replicate": right,
                        **_agreement_summary(repeats[left], repeats[right], align_replicate=False),
                    }
                )
        for left, right in combinations(sorted(judges), 2):
            between.append(
                {
                    **metadata,
                    "left_judge_id": left,
                    "right_judge_id": right,
                    **_agreement_summary(judges[left], judges[right], align_replicate=True),
                }
            )
    return within, between


def _agentic_pairs(rows: list[dict], tasks: list[dict], *, seed: int, resamples: int) -> list[dict]:
    groups: dict[tuple, dict[tuple, dict[str, dict]]] = defaultdict(lambda: defaultdict(dict))
    for task in tasks:
        if task["kind"] == "rating" and task.get("track") == "agentic":
            key = (task["split"], task["target_id"], task["judge_id"])
            pair = (
                task["matched_pair_id"],
                task["context_id"],
                task["generation_replicate"],
                task["rating_replicate"],
            )
            groups[key].setdefault(pair, {})
    for row in rows:
        if row["kind"] != "rating" or row["track"] != "agentic":
            continue
        key = (row["split"], row["target_id"], row["judge_id"])
        pair = (
            row["matched_pair_id"],
            row["context_id"],
            row["generation_replicate"],
            row["rating_replicate"],
        )
        if pair not in groups[key]:
            raise ValidationError("agentic rating is absent from planned tasks")
        if row["protocol_mode"] in groups[key][pair]:
            raise ValidationError("duplicate agentic pair member")
        groups[key][pair][row["protocol_mode"]] = row
    result = []
    for (split, target, judge), pair_groups in sorted(groups.items()):
        pairs = [
            (members["control"], members["prefill_stress"])
            for members in pair_groups.values()
            if set(members) == {"control", "prefill_stress"}
        ]
        dimensions = {}
        for dimension in DIMENSION_WEIGHTS:
            diffs = [
                b["scores"][dimension] - a["scores"][dimension]
                for a, b in pairs
                if dimension in a["scores"] and dimension in b["scores"]
            ]
            if diffs:
                dimensions[dimension] = {"n": len(diffs), "mean": fmean(diffs)}
        transitions = {}
        for label in CRITICAL_FAILURE_PENALTIES:
            cells = _binary_agreement(pairs, label)
            transitions[label] = {
                "both_absent": cells["both_absent"],
                "both_present": cells["both_present"],
                "control_present_stress_absent": cells["left_only"],
                "control_absent_stress_present": cells["right_only"],
            }
        differences = [
            _score([b])["overall_score"] - _score([a])["overall_score"] for a, b in pairs
        ]
        strata: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for (control, _), difference in zip(pairs, differences, strict=True):
            strata[control["category"]][control["family_id"]].append(difference)
        result.append(
            {
                "track": "agentic",
                "split": split,
                "target_id": target,
                "judge_id": judge,
                "planned_pairs": len(pair_groups),
                "complete_pairs": len(pairs),
                "dropped_pairs": len(pair_groups) - len(pairs),
                "planned_context_pairs": len({(pair[0], pair[1]) for pair in pair_groups}),
                "unique_context_pairs": len(
                    {(a["matched_pair_id"], a["context_id"]) for a, _ in pairs}
                ),
                "dimension_differences": dimensions,
                "mean_overall_score_difference": fmean(differences) if differences else None,
                "critical_failure_transitions": transitions,
                "interval": _interval(dict(strata), seed=seed, resamples=resamples, pooled=True),
            }
        )
        result[-1]["interval"]["estimand"] = "mean_matched_stress_minus_control_score"
    return result


def _synthetic_diagnostics(rows: list[dict], fixtures: list[dict], tasks: list[dict]) -> list[dict]:
    definitions = {f["fixture_id"]: f for f in fixtures}
    groups: dict[tuple, list] = defaultdict(list)
    for task in tasks:
        if task["kind"] == "fixture_rating":
            if task["fixture_id"] not in definitions:
                raise ValidationError("planned rating refers to unknown synthetic fixture")
            groups[(task["track"], task["split"], task["judge_id"])].append(task)
    successful = {row["task_id"]: row for row in rows if row["kind"] == "fixture_rating"}
    results = []
    for (track, split, judge), group in sorted(groups.items()):
        completed = [successful[task["task_id"]] for task in group if task["task_id"] in successful]
        lookup = {(r["fixture_id"], r["rating_replicate"]): r for r in completed}
        order = Counter(
            {
                "planned_comparisons": 0,
                "satisfied": 0,
                "ties": 0,
                "reversals": 0,
                "equivalence_violations": 0,
                "missing_comparisons": 0,
            }
        )
        details = []
        styles: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        style_coverage: dict[str, Counter] = defaultdict(Counter)
        useful = {
            (r["scenario_id"], r["rating_replicate"]): r
            for r in completed
            if definitions[r["fixture_id"]]["variant"] == "useful"
        }
        for task in group:
            row = lookup.get((task["fixture_id"], task["rating_replicate"]))
            definition = definitions[task["fixture_id"]]
            for hypothesis in definition.get("hypotheses", []):
                other = lookup.get((hypothesis["other_fixture_id"], task["rating_replicate"]))
                for dimension in hypothesis["dimensions"]:
                    order["planned_comparisons"] += 1
                    if (
                        row is None
                        or other is None
                        or dimension not in other["scores"]
                        or dimension not in row["scores"]
                    ):
                        order["missing_comparisons"] += 1
                        details.append(
                            {
                                "fixture_id": task["fixture_id"],
                                "other_fixture_id": hypothesis["other_fixture_id"],
                                "rating_replicate": task["rating_replicate"],
                                "dimension": dimension,
                                "relation": hypothesis["relation"],
                                "difference": None,
                                "outcome": "missing_comparisons",
                            }
                        )
                        continue
                    difference = row["scores"][dimension] - other["scores"][dimension]
                    relation = hypothesis["relation"]
                    if relation not in {"higher", "equivalent"}:
                        raise ValidationError("unknown synthetic comparison relation")
                    outcome = (
                        "satisfied"
                        if (relation == "higher" and difference > 0)
                        or (relation == "equivalent" and difference == 0)
                        else "equivalence_violations"
                        if relation == "equivalent"
                        else "ties"
                        if difference == 0
                        else "reversals"
                    )
                    order[outcome] += 1
                    details.append(
                        {
                            "fixture_id": row["fixture_id"],
                            "other_fixture_id": other["fixture_id"],
                            "rating_replicate": row["rating_replicate"],
                            "dimension": dimension,
                            "relation": relation,
                            "difference": difference,
                            "outcome": outcome,
                        }
                    )
            variant = definition["variant"]
            baseline = useful.get((task["scenario_id"], task["rating_replicate"]))
            if variant in {"formatting", "verbose"}:
                style_coverage[variant]["planned_pairs"] += 1
                style_coverage[variant]["matched_pairs"] += int(
                    row is not None and baseline is not None
                )
                style_coverage[variant]["missing_pairs"] += int(row is None or baseline is None)
            if variant in {"formatting", "verbose"} and row is not None and baseline is not None:
                for dimension in set(row["scores"]) & set(baseline["scores"]):
                    styles[variant][dimension].append(
                        row["scores"][dimension] - baseline["scores"][dimension]
                    )
        results.append(
            {
                "track": track,
                "split": split,
                "judge_id": judge,
                "origin": "synthetic_authored",
                "expectation_source": "author_declared",
                "planned_rating_count": len(group),
                "rating_count": len(completed),
                "missing_rating_count": len(group) - len(completed),
                "ordering": dict(order),
                "comparisons": details,
                "style_sensitivity": {
                    variant: {
                        dim: {
                            "n": len(values),
                            "mean_delta": fmean(values),
                            "mean_absolute_delta": fmean(abs(v) for v in values),
                        }
                        for dim, values in sorted(by_dim.items())
                    }
                    for variant, by_dim in sorted(styles.items())
                },
                "style_coverage": {
                    variant: dict(counts) for variant, counts in sorted(style_coverage.items())
                },
                "verbosity_equivalence": "author_declared_unverified",
            }
        )
    return results


def _coverage(tasks: list[dict]) -> dict[str, Any]:
    by_kind: dict[str, Counter] = defaultdict(Counter)
    errors = Counter()
    attempts = retries = failed = 0
    for task in tasks:
        status = task["status"]
        if status not in {"pending", "complete", "error"}:
            raise ValidationError("unsupported task execution status")
        by_kind[task["kind"]][status] += 1
        history = task.get("attempts", [])
        attempts += len(history)
        retries += max(0, len(history) - 1)
        for attempt in history:
            if attempt["status"] == "error":
                failed += 1
                errors[attempt.get("error_type", "unspecified")] += 1
    complete = sum(t["status"] == "complete" for t in tasks)
    return {
        "planned_tasks": len(tasks),
        "completed_tasks": complete,
        "incomplete_tasks": len(tasks) - complete,
        "attempts": attempts,
        "retries": retries,
        "failed_attempts": failed,
        "errors_by_type": dict(sorted(errors.items())),
        "by_kind": {k: dict(sorted(v.items())) for k, v in sorted(by_kind.items())},
    }


def _disclose_model_relationships(report: dict, manifest: dict) -> None:
    """Keep declared self-judgment separate without claiming authenticated identity."""
    targets = {item["id"]: item for item in manifest.get("targets", [])}
    judges = {item["id"]: item for item in manifest.get("judges", [])}
    report["family_declarations"] = {
        "targets": {key: item["family"] for key, item in sorted(targets.items())},
        "judges": {key: item["family"] for key, item in sorted(judges.items())},
    }

    def reasons(left, right):
        result = []
        if left["family"] == right["family"]:
            result.append("same_declared_family")
        if left["model"] == right["model"]:
            result.append("same_declared_model")
        return result

    report["self_judging_pairs"] = [
        [target_id, judge_id]
        for target_id, target in sorted(targets.items())
        for judge_id, judge in sorted(judges.items())
        if reasons(target, judge)
    ]
    report["relationship_evidence"] = "manifest_declarations_not_authenticated"

    def annotate(group):
        try:
            target, judge = targets[group["target_id"]], judges[group["judge_id"]]
        except KeyError as exc:
            raise ValidationError(
                "rating model identity missing from manifest declarations"
            ) from exc
        related = reasons(target, judge)
        group.update(
            candidate_family=target["family"],
            candidate_model=target["model"],
            judge_family=judge["family"],
            judge_model=judge["model"],
            self_judging=bool(related),
            self_judging_reasons=related,
        )

    for key, separate in (
        ("candidate_results", "self_judged_results"),
        ("agentic_pairs", "self_judged_agentic_pairs"),
    ):
        ordinary, self_judged = [], []
        for group in report[key]:
            annotate(group)
            (self_judged if group["self_judging"] else ordinary).append(group)
        report[key], report[separate] = ordinary, self_judged

    ordinary, self_judged = [], []
    for group in report["candidate_contrasts"]:
        left, right = targets[group["left_target_id"]], targets[group["right_target_id"]]
        judge = judges[group["judge_id"]]
        left_reasons, right_reasons = reasons(left, judge), reasons(right, judge)
        group.update(
            left_candidate_family=left["family"],
            right_candidate_family=right["family"],
            judge_family=judge["family"],
            judge_model=judge["model"],
            left_self_judging=bool(left_reasons),
            right_self_judging=bool(right_reasons),
            left_self_judging_reasons=left_reasons,
            right_self_judging_reasons=right_reasons,
        )
        (self_judged if left_reasons or right_reasons else ordinary).append(group)
    report["candidate_contrasts"], report["self_judged_contrasts"] = ordinary, self_judged

    for group in report["within_judge_agreement"]:
        if group["target_id"] is not None:
            annotate(group)
        else:
            judge = judges[group["judge_id"]]
            group.update(judge_family=judge["family"], judge_model=judge["model"])

    for group in report["between_judge_agreement"]:
        left, right = judges[group["left_judge_id"]], judges[group["right_judge_id"]]
        related = reasons(left, right)
        group.update(
            left_judge_family=left["family"],
            right_judge_family=right["family"],
            left_judge_model=left["model"],
            right_judge_model=right["model"],
            same_declared_family="same_declared_family" in related,
            same_declared_model="same_declared_model" in related,
            family_relationship=(
                "same_declared_family"
                if left["family"] == right["family"]
                else "different_declared_families"
            ),
            independence_warning=(
                "Judges share a declared family or model; agreement is not independent evidence."
                if related
                else "Different declared families do not establish independent models or errors."
            ),
        )
        target = targets.get(group["target_id"])
        group["left_self_judging"] = bool(target and reasons(target, left))
        group["right_self_judging"] = bool(target and reasons(target, right))


def build_study_report(state: dict[str, Any]) -> dict[str, Any]:
    """Compute a deterministic report from a content-validated study state."""
    rows = state["rows"]
    _validate_rows(rows)
    status = state["execution_status"]
    if status not in {"not_run", "partial", "complete"}:
        raise ValidationError("invalid execution status")
    within, between = _agreements(rows)
    coverage = _coverage(state["tasks"])
    seed = state["manifest"].get("analysis_seed", _SEED)
    resamples = state["manifest"].get("bootstrap_resamples", _RESAMPLES)
    report = {
        "tool": "HumanAI-Impact-Bench",
        "report_version": "0.8",
        "study_id": state["manifest"]["study_id"],
        "manifest_digest": record_digest(state["manifest"]),
        "evidence_stage": "PREVIEW",
        "human_review": "not_performed",
        "deployment_action": "HOLD",
        "execution_status": status,
        "comparison_complete": status == "complete",
        "coverage": coverage,
        "analysis": {"seed": seed, "bootstrap_resamples": resamples, "unit": "concept_family"},
        "candidate_results": _candidate_results(rows, seed=seed, resamples=resamples),
        "candidate_contrasts": _candidate_contrasts(rows, seed=seed, resamples=resamples),
        "within_judge_agreement": within,
        "between_judge_agreement": between,
        "agentic_pairs": _agentic_pairs(rows, state["tasks"], seed=seed, resamples=resamples),
        "synthetic_diagnostics": _synthetic_diagnostics(rows, state["fixtures"], state["tasks"]),
        "limitations": [
            "Automated judge agreement is consistency evidence, not human-rated accuracy.",
            "Results are conditional on the authored scenarios and supplied model configurations.",
            "Synthetic expectations are author-declared hypotheses, not human gold labels.",
            "Repeated ratings do not increase independent scenario or family counts.",
            "Model and family relationships are declarations, not authenticated identities.",
        ],
    }
    _disclose_model_relationships(report, state["manifest"])
    if status != "complete":

        def suppress_intervals(value):
            if isinstance(value, dict):
                if "interval" in value:
                    value["interval"].update(lower=None, upper=None, reason="incomplete_study")
                for child in value.values():
                    suppress_intervals(child)
            elif isinstance(value, list):
                for child in value:
                    suppress_intervals(child)

        suppress_intervals(report)
    return report


def report_study(*, manifest_path: Path, run_root: Path, output_path: Path) -> dict[str, Any]:
    """Validate underlying study artifacts, recompute, and atomically write a report."""
    from humanai_impact_bench.experiments import validate_study_state

    output = Path(output_path)
    root = Path(run_root).resolve()
    if any(output.resolve().is_relative_to(root / name) for name in ("inputs", "tasks")):
        raise ValidationError("report output must not overwrite study inputs")
    if output.resolve() in {
        Path(manifest_path).resolve(),
        (Path(run_root) / "study-state.json").resolve(),
    }:
        raise ValidationError("report output must not overwrite study inputs")
    state = validate_study_state(Path(manifest_path), Path(run_root))
    report = build_study_report(state)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent, prefix=f".{output.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return report
