from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from humanai_impact_bench.validation import (
    ValidationError,
    load_annotations,
    load_scenarios,
    validate_annotation,
    validate_scenario,
)


def write_jsonl(path: Path, records: list[Any]) -> Path:
    path.write_text(
        "\n".join(json.dumps(record, allow_nan=True) for record in records) + "\n",
        encoding="utf-8",
    )
    return path


def test_load_scenarios_returns_clean_records_and_skips_blank_lines(
    tmp_path: Path,
    scenario_factory: Callable[..., dict[str, Any]],
) -> None:
    scenario = scenario_factory()
    path = tmp_path / "scenarios.jsonl"
    path.write_text(f"\n{json.dumps(scenario)}\n\n", encoding="utf-8")

    assert load_scenarios(path) == [scenario]
    assert "_source_line" not in scenario


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"benchmark_version": "0.3"}, "benchmark_version"),
        ({"scenario_id": "Invalid ID"}, "scenario_id"),
        ({"language": "fr"}, "language"),
        ({"language": []}, "language"),
        ({"title": "x"}, "title"),
        ({"category": "unknown"}, "unknown category"),
        ({"category": []}, "category"),
        ({"risk_level": "extreme"}, "unknown risk level"),
        ({"context": "short"}, "context"),
        ({"initial_prompt": ""}, "initial_prompt"),
        ({"persona": []}, "persona must be an object"),
        ({"follow_up_prompts": []}, "follow_up_prompts"),
        ({"follow_up_prompts": [1]}, "follow_up_prompts items"),
        ({"expected_behaviors": [""]}, "expected_behaviors items"),
        ({"failure_modes": "failure"}, "failure_modes"),
        ({"dimensions": ["not_a_dimension"]}, "unknown dimensions"),
        (
            {"dimensions": ["healthy_boundaries", "healthy_boundaries"]},
            "dimensions items must be unique",
        ),
        ({"tags": ["same", "same"]}, "tags items must be unique"),
        ({"tags": [1]}, "tags items"),
    ],
)
def test_validate_scenario_rejects_invalid_fields(
    scenario_factory: Callable[..., dict[str, Any]],
    override: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        validate_scenario(scenario_factory(**override))


def test_validate_scenario_requires_schema_fields(
    scenario_factory: Callable[..., dict[str, Any]],
) -> None:
    scenario = scenario_factory()
    del scenario["tags"]

    with pytest.raises(ValidationError, match="missing fields: tags"):
        validate_scenario(scenario)


def test_validate_scenario_rejects_unexpected_top_level_field(
    scenario_factory: Callable[..., dict[str, Any]],
) -> None:
    with pytest.raises(ValidationError, match="unexpected fields: surprise"):
        validate_scenario(scenario_factory(surprise=True))


@pytest.mark.parametrize(
    ("persona", "message"),
    [
        (
            {"situation": "A situation", "communication_style": "Direct"},
            "missing fields: age_group",
        ),
        (
            {
                "age_group": "adult",
                "situation": "A situation",
                "communication_style": "Direct",
                "unknown": "value",
            },
            "unexpected persona fields: unknown",
        ),
        (
            {
                "age_group": "",
                "situation": "A situation",
                "communication_style": "Direct",
            },
            "age_group",
        ),
        (
            {
                "age_group": "adult",
                "situation": "A situation",
                "communication_style": "Direct",
                "vulnerability_factors": ["loneliness", "loneliness"],
            },
            "vulnerability_factors items must be unique",
        ),
    ],
)
def test_validate_scenario_checks_persona_contract(
    scenario_factory: Callable[..., dict[str, Any]],
    persona: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        validate_scenario(scenario_factory(persona=persona))


def test_load_scenarios_allows_same_id_in_different_languages(
    tmp_path: Path,
    scenario_factory: Callable[..., dict[str, Any]],
) -> None:
    records = [scenario_factory(), scenario_factory(language="vi")]

    assert len(load_scenarios(write_jsonl(tmp_path / "scenarios.jsonl", records))) == 2


def test_validate_scenario_accepts_v02_reality_testing_contract(
    scenario_factory: Callable[..., dict[str, Any]],
) -> None:
    scenario = scenario_factory(
        benchmark_version="0.2",
        category="reality_testing",
        dimensions=[
            "epistemic_grounding",
            "memory_integrity",
            "reality_testing_support",
            "correction_responsiveness",
        ],
    )

    validate_scenario(scenario)


def test_load_scenarios_rejects_duplicate_id_language_pair(
    tmp_path: Path,
    scenario_factory: Callable[..., dict[str, Any]],
) -> None:
    path = write_jsonl(tmp_path / "scenarios.jsonl", [scenario_factory(), scenario_factory()])

    with pytest.raises(ValidationError, match="duplicate scenario_id/language pair"):
        load_scenarios(path)


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("", "no records found"),
        ("\n\n", "no records found"),
        ("not-json\n", "invalid JSON"),
        ("[]\n", "expected a JSON object"),
    ],
)
def test_load_scenarios_reports_file_errors(
    tmp_path: Path,
    contents: str,
    message: str,
) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValidationError, match=message):
        load_scenarios(path)


def test_load_scenarios_reports_source_line_for_invalid_record(
    tmp_path: Path,
    scenario_factory: Callable[..., dict[str, Any]],
) -> None:
    invalid = scenario_factory(language="fr")
    path = tmp_path / "scenarios.jsonl"
    path.write_text(f"\n{json.dumps(invalid)}\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="scenario at line 2"):
        load_scenarios(path)


def test_load_scenarios_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="file not found"):
        load_scenarios(tmp_path / "missing.jsonl")


def test_load_scenarios_wraps_other_file_errors(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="could not read"):
        load_scenarios(tmp_path)


def test_jsonl_rejects_reserved_internal_field(
    tmp_path: Path,
    scenario_factory: Callable[..., dict[str, Any]],
) -> None:
    path = write_jsonl(
        tmp_path / "scenarios.jsonl",
        [scenario_factory(_source_line=99)],
    )

    with pytest.raises(ValidationError, match="reserved field '_source_line'"):
        load_scenarios(path)


def test_load_annotations_returns_valid_records(
    tmp_path: Path,
    annotation_factory: Callable[..., dict[str, Any]],
) -> None:
    annotation = annotation_factory()

    assert load_annotations(write_jsonl(tmp_path / "annotations.jsonl", [annotation])) == [
        annotation
    ]


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"scenario_id": ""}, "scenario_id"),
        ({"language": "fr"}, "language"),
        ({"model": 7}, "model"),
        ({"rater_id": ""}, "rater_id"),
        ({"scores": {}}, "scores must be a non-empty object"),
        ({"scores": {1: 3}}, "score dimension names must be strings"),
        ({"scores": {"unknown": 3}}, "unknown score dimensions"),
        ({"scores": {"healthy_boundaries": True}}, "score must be between 1 and 5"),
        ({"scores": {"healthy_boundaries": 0}}, "score must be between 1 and 5"),
        ({"scores": {"healthy_boundaries": 6}}, "score must be between 1 and 5"),
        ({"scores": {"healthy_boundaries": float("nan")}}, "score must be between 1 and 5"),
        ({"critical_failures": "none"}, "critical_failures must be an array"),
        ({"critical_failures": [1]}, "critical_failures items"),
        ({"critical_failures": ["unknown"]}, "unknown critical failures"),
    ],
)
def test_validate_annotation_rejects_invalid_fields(
    annotation_factory: Callable[..., dict[str, Any]],
    override: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        validate_annotation(annotation_factory(**override))


def test_load_annotations_rejects_duplicate_rating_identity(
    tmp_path: Path,
    annotation_factory: Callable[..., dict[str, Any]],
) -> None:
    path = write_jsonl(
        tmp_path / "annotations.jsonl",
        [annotation_factory(), annotation_factory()],
    )

    with pytest.raises(
        ValidationError,
        match="duplicate scenario_id/language/model/rater_id tuple",
    ):
        load_annotations(path)


def test_load_annotations_allows_same_rating_identity_in_different_languages(
    tmp_path: Path,
    annotation_factory: Callable[..., dict[str, Any]],
) -> None:
    records = [annotation_factory(language="en"), annotation_factory(language="vi")]

    assert len(load_annotations(write_jsonl(tmp_path / "annotations.jsonl", records))) == 2


@pytest.mark.parametrize(
    "critical_failure",
    [
        "delusion_reinforcement",
        "persecutory_escalation",
        "false_memory_implantation",
        "fabricated_shared_history",
        "reality_testing_suppression",
        "epistemic_dependency_reinforcement",
    ],
)
def test_validate_annotation_accepts_v02_scores_and_failures(
    annotation_factory: Callable[..., dict[str, Any]],
    critical_failure: str,
) -> None:
    annotation = annotation_factory(
        scores={
            "epistemic_grounding": 4,
            "memory_integrity": 5,
            "reality_testing_support": 4,
            "correction_responsiveness": 5,
        },
        critical_failures=[critical_failure],
    )

    validate_annotation(annotation)


def test_load_annotations_allows_different_raters(
    tmp_path: Path,
    annotation_factory: Callable[..., dict[str, Any]],
) -> None:
    path = write_jsonl(
        tmp_path / "annotations.jsonl",
        [annotation_factory(), annotation_factory(rater_id="rater-002")],
    )

    assert len(load_annotations(path)) == 2
