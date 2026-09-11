from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from humanai_impact_bench.constants import SUPPORTED_BENCHMARK_VERSIONS
from humanai_impact_bench.validation import ValidationError, validate_scenario

ROOT = Path(__file__).resolve().parents[1]
COVERAGE_STANDARD = json.loads(
    (ROOT / "configs" / "scenario-coverage-standard.json").read_text(encoding="utf-8")
)
SCENARIO_SCHEMA = json.loads(
    (ROOT / "schemas" / "scenario.schema.json").read_text(encoding="utf-8")
)


def test_v06_uses_the_legacy_fourteen_field_contract(scenario_factory) -> None:
    scenario = scenario_factory(benchmark_version="0.6")

    validate_scenario(scenario)
    assert len(scenario) == 14

    scenario["locale"] = "en-US"
    with pytest.raises(ValidationError, match="unexpected fields: locale"):
        validate_scenario(scenario)


def test_v06_is_registered_in_code_and_schema() -> None:
    assert "0.6" in SUPPORTED_BENCHMARK_VERSIONS
    assert "0.6" in SCENARIO_SCHEMA["properties"]["benchmark_version"]["enum"]


def test_v06_rejects_v07_only_categories(scenario_factory) -> None:
    scenario = scenario_factory(
        benchmark_version="0.6",
        category="delegated_action_authorization",
    )

    with pytest.raises(ValidationError, match="unknown category"):
        validate_scenario(scenario)
    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(SCENARIO_SCHEMA).validate(scenario)


def test_v06_coverage_arithmetic_and_category_partition() -> None:
    config = COVERAGE_STANDARD["v0.6"]
    categories = set(config["categories"])
    bilingual = set(config["bilingual_categories"])
    english_first = set(config["english_first_categories"])
    current_stage_categories = set(config["current_stage_categories"])
    stage1 = config["stage1_foundation"]

    assert len(categories) == config["planned_category_count"] == 24
    assert len(bilingual) == config["bilingual_category_count"] == 16
    assert len(english_first) == 8
    assert bilingual.isdisjoint(english_first)
    assert bilingual | english_first == categories
    assert config["current_stage"] == "first_complete_checkpoint"
    assert current_stage_categories == categories
    assert set(stage1["categories"]) == english_first - {"trust_and_anthropomorphism"}
    assert stage1["records_per_category"] == 30
    assert stage1["total_records"] == 210
    assert config["current_stage_records_per_category"] == 50
    assert config["current_stage_total_records"] == 1200

    bilingual_checkpoint = (
        len(bilingual)
        * config["first_complete_checkpoint_records_per_language_in_bilingual_category"]
        * 2
    )
    english_checkpoint = (
        len(english_first) * config["first_complete_checkpoint_records_per_category"]
    )
    assert bilingual_checkpoint == 800
    assert english_checkpoint == 400
    assert (
        bilingual_checkpoint + english_checkpoint
        == config["first_complete_checkpoint_total_records"]
        == 1200
    )

    assert (
        config["planned_category_count"] * config["mature_records_per_category"]
        == config["planned_total_records"]
        == 2400
    )
