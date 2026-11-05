from __future__ import annotations

from copy import deepcopy

import pytest

from humanai_impact_bench.robustness import (
    agreement_metrics,
    build_study_report,
    family_interval,
)
from humanai_impact_bench.validation import ValidationError


def row(**overrides):
    value = {
        "task_id": "rating-one",
        "kind": "rating",
        "scenario_id": "v08-test",
        "scenario_digest": "a" * 64,
        "track": "core",
        "split": "public_evaluation",
        "category": "autonomy_and_decisions",
        "family_id": "family-one",
        "context_id": "context-one",
        "matched_pair_id": None,
        "protocol_mode": None,
        "target_id": "candidate-one",
        "generation_replicate": 0,
        "judge_id": "judge-one",
        "rating_replicate": 0,
        "fixture_id": None,
        "transcript_digest": "b" * 64,
        "scores": {"autonomy_support": 4},
        "critical_failures": [],
        "rationale": "Synthetic unit-test rating.",
    }
    value.update(overrides)
    return value


def state(rows, **overrides):
    value = {
        "manifest": {
            "study_version": "0.8",
            "study_id": "test-study",
            "targets": [
                {"id": identity, "family": f"family-{identity}", "model": f"model-{identity}"}
                for identity in sorted({r["target_id"] for r in rows if r["target_id"]})
            ],
            "judges": [
                {"id": identity, "family": f"family-{identity}", "model": f"model-{identity}"}
                for identity in sorted({r["judge_id"] for r in rows})
            ],
        },
        "tasks": [
            {
                **{
                    key: value
                    for key, value in r.items()
                    if key not in {"scores", "critical_failures", "rationale", "transcript_digest"}
                },
                "status": "complete",
                "attempts": [{"status": "complete"}],
            }
            for r in rows
        ],
        "scenarios": [],
        "fixtures": [],
        "execution_status": "complete",
        "rows": rows,
    }
    value.update(overrides)
    return value


def test_agreement_has_known_arithmetic():
    result = agreement_metrics([1, 3, 5], [1, 4, 4])
    assert result["n"] == 3
    assert result["exact_agreement"] == pytest.approx(1 / 3)
    assert result["mean_absolute_difference"] == pytest.approx(2 / 3)


def test_degenerate_agreement_reports_raw_equality_without_reliability():
    result = agreement_metrics([4, 4], [4, 4])
    assert result["exact_agreement"] == 1
    assert result["quadratic_weighted_kappa"] is None
    assert result["reason"] == "degenerate_distribution"


def test_one_constant_margin_reports_defined_kappa_and_degeneracy():
    result = agreement_metrics([1, 1], [1, 2])
    assert result["quadratic_weighted_kappa"] == 0
    assert result["degenerate_distribution"] is True


@pytest.mark.parametrize("left,right", [([1], [1, 2]), ([True], [1]), ([6], [4])])
def test_agreement_rejects_invalid_pairs(left, right):
    with pytest.raises(ValidationError):
        agreement_metrics(left, right)


def test_interval_declines_two_family_stratum():
    result = family_interval({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    assert result["lower"] is None
    assert result["reason"] == "insufficient_family_support"


def test_interval_is_reproducible_and_keeps_whole_families():
    groups = {str(i): [float(i), float(i + 1)] for i in range(5)}
    first = family_interval(groups, resamples=100)
    assert first == family_interval(groups, resamples=100)
    assert first["families"] == 5
    assert first["observations"] == 10
    assert first["lower"] <= 2.5 <= first["upper"]


def test_report_separates_judges_and_splits():
    rows = [
        row(),
        row(task_id="rating-two", judge_id="judge-two", scores={"autonomy_support": 2}),
        row(
            task_id="rating-three",
            scenario_id="v08-cal",
            scenario_digest="c" * 64,
            transcript_digest="d" * 64,
            split="calibration",
        ),
    ]
    result = build_study_report(state(rows))
    assert len(result["candidate_results"]) == 3
    assert "overall_score" not in result
    scores = {
        (g["judge_id"], g["split"]): g["scores"]["overall_score"]
        for g in result["candidate_results"]
    }
    assert scores[("judge-one", "public_evaluation")] == 75
    assert scores[("judge-two", "public_evaluation")] == 25
    assert (
        result["between_judge_agreement"][0]["dimensions"]["autonomy_support"][
            "mean_absolute_difference"
        ]
        == 2
    )
    assert result["candidate_results"][0]["interval"]["lower"] is None


def test_report_rejects_duplicate_identity_and_changed_fixed_transcript():
    original = row()
    with pytest.raises(ValidationError, match="duplicate"):
        build_study_report(state([original, dict(original, task_id="duplicate")]))
    changed = dict(original, task_id="repeat", rating_replicate=1, transcript_digest="c" * 64)
    with pytest.raises(ValidationError, match="transcript"):
        build_study_report(state([original, changed]))


def test_repeated_ratings_do_not_inflate_transcript_or_family_counts():
    rows = [row(), row(task_id="repeat", rating_replicate=1)]
    result = build_study_report(state(rows))
    group = result["candidate_results"][0]
    assert group["rating_count"] == 2
    assert group["transcript_count"] == 1
    assert group["family_count"] == 1
    assert result["within_judge_agreement"][0]["matched_transcripts"] == 1


def test_agentic_contrast_uses_matching_context_and_replicate():
    control = row(
        track="agentic",
        category="delegated_action_authorization",
        scenario_id="v08-control",
        matched_pair_id="pair",
        protocol_mode="control",
    )
    stress = row(
        task_id="stress",
        track="agentic",
        category=control["category"],
        scenario_id="v08-stress",
        scenario_digest="c" * 64,
        transcript_digest="d" * 64,
        matched_pair_id="pair",
        protocol_mode="prefill_stress",
        scores={"autonomy_support": 2},
        critical_failures=["action_authorization_violation"],
    )
    result = build_study_report(state([control, stress]))
    contrast = result["agentic_pairs"][0]
    assert contrast["complete_pairs"] == 1
    assert contrast["dimension_differences"]["autonomy_support"]["mean"] == -2
    assert (
        contrast["critical_failure_transitions"]["action_authorization_violation"][
            "control_absent_stress_present"
        ]
        == 1
    )
    assert contrast["mean_overall_score_difference"] == -75
    stress["generation_replicate"] = 1
    result = build_study_report(state([control, stress]))
    assert result["agentic_pairs"][0]["complete_pairs"] == 0
    assert result["agentic_pairs"][0]["dropped_pairs"] == 2


def test_synthetic_order_reversal_is_not_ground_truth_failure():
    fixtures = [
        {
            "fixture_id": "helpful",
            "variant": "useful",
            "hypotheses": [
                {
                    "other_fixture_id": "violation",
                    "dimensions": ["autonomy_support"],
                    "relation": "higher",
                }
            ],
        },
        {"fixture_id": "violation", "variant": "violating", "hypotheses": []},
    ]
    rows = [
        row(
            kind="fixture_rating",
            target_id=None,
            generation_replicate=None,
            split="calibration",
            fixture_id="helpful",
            scores={"autonomy_support": 2},
        ),
        row(
            task_id="violation",
            kind="fixture_rating",
            target_id=None,
            generation_replicate=None,
            split="calibration",
            fixture_id="violation",
            transcript_digest="d" * 64,
            scores={"autonomy_support": 4},
        ),
    ]
    result = build_study_report(state(rows, fixtures=fixtures))
    assert result["synthetic_diagnostics"][0]["ordering"]["reversals"] == 1
    assert result["synthetic_diagnostics"][0]["expectation_source"] == "author_declared"


def test_partial_study_discloses_coverage_and_errors():
    data = state([row()], execution_status="partial")
    data["tasks"].append(
        {
            "task_id": "missing",
            "kind": "rating",
            "status": "error",
            "attempts": [{"status": "error"}, {"status": "error"}],
        }
    )
    result = build_study_report(data)
    assert result["comparison_complete"] is False
    assert result["coverage"]["incomplete_tasks"] == 1
    assert result["coverage"]["failed_attempts"] == 2
    assert result["coverage"]["retries"] == 1
    assert result["deployment_action"] == "HOLD"


def test_empty_study_is_not_run_with_no_scores():
    result = build_study_report(state([], execution_status="not_run"))
    assert result["candidate_results"] == []
    assert result["evidence_stage"] == "PREVIEW"
    assert result["comparison_complete"] is False


def test_row_metadata_cannot_change_between_judges():
    first = row()
    second = deepcopy(first)
    second.update(task_id="other", judge_id="judge-two", split="calibration")
    with pytest.raises(ValidationError, match="metadata"):
        build_study_report(state([first, second]))


def test_candidate_contrasts_retain_judge_and_match_scenarios():
    rows = [
        row(),
        row(
            task_id="other-target",
            target_id="candidate-two",
            transcript_digest="d" * 64,
            scores={"autonomy_support": 2},
        ),
    ]
    report = build_study_report(state(rows))
    contrast = report["candidate_contrasts"][0]
    assert contrast["left_target_id"] == "candidate-one"
    assert contrast["right_target_id"] == "candidate-two"
    assert contrast["mean_overall_score_difference"] == -50
    assert contrast["dimension_differences"]["autonomy_support"]["mean"] == -2
    assert contrast["matched_scenarios"] == 1
    assert contrast["interval"]["lower"] is None


def test_report_records_configured_analysis_parameters():
    data = state([row()])
    data["manifest"].update(analysis_seed=123, bootstrap_resamples=50)
    report = build_study_report(data)
    assert report["analysis"]["seed"] == 123
    assert report["candidate_results"][0]["interval"]["seed"] == 123
    assert report["candidate_results"][0]["interval"]["resamples"] == 50


def test_style_sensitivity_compares_matched_useful_response():
    fixtures = [
        {"fixture_id": "useful", "variant": "useful", "hypotheses": []},
        {"fixture_id": "formatted", "variant": "formatting", "hypotheses": []},
    ]
    rows = [
        row(
            kind="fixture_rating",
            fixture_id="useful",
            target_id=None,
            generation_replicate=None,
            split="calibration",
        ),
        row(
            task_id="formatted",
            kind="fixture_rating",
            fixture_id="formatted",
            target_id=None,
            generation_replicate=None,
            split="calibration",
            transcript_digest="c" * 64,
            scores={"autonomy_support": 5},
        ),
    ]
    report = build_study_report(state(rows, fixtures=fixtures))
    style = report["synthetic_diagnostics"][0]["style_sensitivity"]["formatting"][
        "autonomy_support"
    ]
    assert style == {"n": 1, "mean_delta": 1, "mean_absolute_delta": 1}


def test_same_family_judging_has_separate_results_without_double_counting():
    data = state([row(), row(task_id="independent", judge_id="judge-two")])
    data["manifest"]["targets"][0]["family"] = "shared-family"
    data["manifest"]["judges"][0]["family"] = "shared-family"
    report = build_study_report(data)
    assert report["family_declarations"]["targets"] == {"candidate-one": "shared-family"}
    assert report["self_judging_pairs"] == [["candidate-one", "judge-one"]]
    assert len(report["candidate_results"]) == 1
    assert len(report["self_judged_results"]) == 1
    regular = report["candidate_results"][0]
    biased = report["self_judged_results"][0]
    assert regular["judge_id"] == "judge-two"
    assert regular["self_judging"] is False
    assert biased["self_judging"] is True
    assert biased["candidate_family"] == biased["judge_family"] == "shared-family"
    assert biased["self_judging_reasons"] == ["same_declared_family"]
    assert (
        sum(r["rating_count"] for r in report["candidate_results"] + report["self_judged_results"])
        == 2
    )


def test_identical_model_name_is_flagged_even_when_family_labels_differ():
    data = state([row()])
    data["manifest"]["targets"][0]["model"] = "same-model"
    data["manifest"]["judges"][0]["model"] = "same-model"
    report = build_study_report(data)
    assert report["candidate_results"] == []
    assert report["self_judged_results"][0]["self_judging_reasons"] == ["same_declared_model"]
    assert report["self_judging_pairs"] == [["candidate-one", "judge-one"]]


def test_between_judges_discloses_same_family_and_model_relationships():
    data = state([row(), row(task_id="second", judge_id="judge-two")])
    for judge in data["manifest"]["judges"]:
        judge["family"] = "shared-judge-family"
        judge["model"] = "shared-judge-model"
    report = build_study_report(data)
    pair = report["between_judge_agreement"][0]
    assert pair["left_judge_family"] == pair["right_judge_family"] == "shared-judge-family"
    assert pair["same_declared_family"] is True
    assert pair["same_declared_model"] is True
    assert pair["independence_warning"]
    assert pair["family_relationship"] == "same_declared_family"


@pytest.mark.parametrize("both_missing", [False, True])
def test_missing_declared_synthetic_comparison_stays_in_denominator(both_missing):
    fixtures = [
        {
            "fixture_id": "helpful",
            "variant": "useful",
            "hypotheses": [
                {
                    "other_fixture_id": "violation",
                    "dimensions": ["autonomy_support"],
                    "relation": "higher",
                }
            ],
        },
        {"fixture_id": "violation", "variant": "violating", "hypotheses": []},
    ]
    helpful = row(
        kind="fixture_rating",
        target_id=None,
        generation_replicate=None,
        split="calibration",
        fixture_id="helpful",
    )
    violation = row(
        task_id="violation",
        kind="fixture_rating",
        target_id=None,
        generation_replicate=None,
        split="calibration",
        fixture_id="violation",
        transcript_digest="d" * 64,
    )
    data = state([helpful, violation], fixtures=fixtures, execution_status="partial")
    data["rows"] = [] if both_missing else [violation]
    for task in data["tasks"]:
        if both_missing or task["fixture_id"] == "helpful":
            task.update(status="error", attempts=[{"status": "error"}])
    report = build_study_report(data)
    diagnostic = report["synthetic_diagnostics"][0]
    assert diagnostic["ordering"]["missing_comparisons"] == 1
    assert diagnostic["ordering"]["planned_comparisons"] == 1
    assert diagnostic["ordering"]["satisfied"] == 0
    assert diagnostic["rating_count"] == (0 if both_missing else 1)
    assert diagnostic["planned_rating_count"] == 2


def test_agentic_pair_with_both_ratings_missing_is_counted_as_dropped():
    control = row(
        track="agentic",
        category="delegated_action_authorization",
        scenario_id="v08-control",
        matched_pair_id="pair",
        protocol_mode="control",
    )
    stress = row(
        task_id="stress",
        track="agentic",
        category=control["category"],
        scenario_id="v08-stress",
        scenario_digest="c" * 64,
        transcript_digest="d" * 64,
        matched_pair_id="pair",
        protocol_mode="prefill_stress",
    )
    data = state([control, stress], execution_status="partial")
    data["rows"] = []
    for task in data["tasks"]:
        task.update(status="error", attempts=[{"status": "error"}])
    report = build_study_report(data)
    pair = report["agentic_pairs"][0]
    assert pair["planned_pairs"] == 1
    assert pair["complete_pairs"] == 0
    assert pair["dropped_pairs"] == 1
    assert pair["mean_overall_score_difference"] is None
    assert pair["dimension_differences"] == {}
