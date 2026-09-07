from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from humanai_impact_bench.constants import SUPPORTED_BENCHMARK_VERSIONS
from humanai_impact_bench.constants import V07_CATEGORIES as REGISTERED_V07_CATEGORIES
from humanai_impact_bench.validation import ValidationError, validate_scenario

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "scenario.schema.json").read_text(encoding="utf-8"))
V07_CATEGORIES = {
    "cross_session_memory_governance",
    "personalized_persuasion_and_steering",
    "delegated_action_authorization",
    "trajectory_recovery_and_correction",
}


def test_v07_core_requires_only_track_plus_legacy_fields(scenario_factory):
    scenario = scenario_factory(benchmark_version="0.7", benchmark_track="core")
    validate_scenario(scenario)
    assert len(scenario) == 15


def test_v07_agentic_prefill_stress_requires_history(scenario_factory):
    scenario = scenario_factory(
        benchmark_version="0.7",
        benchmark_track="agentic",
        category="trajectory_recovery_and_correction",
        locale="en-US",
        protocol_mode="prefill_stress",
        matched_pair_id="trajectory-en-us-pair-001",
        prefill_messages=[
            {"role": "user", "content": "Synthetic prior request."},
            {"role": "assistant", "content": "Synthetic unsafe prior response."},
        ],
    )
    validate_scenario(scenario)


def test_v07_core_rejects_agentic_fields(scenario_factory):
    scenario = scenario_factory(
        benchmark_version="0.7",
        benchmark_track="core",
        locale="en-US",
    )
    with pytest.raises(ValidationError, match="core.*locale"):
        validate_scenario(scenario)


@pytest.mark.parametrize("track", [None, "experimental"])
def test_v07_rejects_missing_or_unknown_track(scenario_factory, track):
    scenario = scenario_factory(benchmark_version="0.7")
    if track is not None:
        scenario["benchmark_track"] = track

    with pytest.raises(ValidationError, match="benchmark_track"):
        validate_scenario(scenario)


def test_v07_agentic_control_omits_prefill_messages(scenario_factory):
    scenario = scenario_factory(
        benchmark_version="0.7",
        benchmark_track="agentic",
        locale="en-US",
        protocol_mode="control",
        matched_pair_id="trajectory-en-us-pair-001",
    )
    validate_scenario(scenario)

    scenario["prefill_messages"] = [
        {"role": "user", "content": "Synthetic prior request."},
        {"role": "assistant", "content": "Synthetic prior response."},
    ]
    with pytest.raises(ValidationError, match="control protocol must omit"):
        validate_scenario(scenario)


@pytest.mark.parametrize("missing_field", ["locale", "protocol_mode", "matched_pair_id"])
def test_v07_agentic_requires_protocol_fields(scenario_factory, missing_field):
    scenario = scenario_factory(
        benchmark_version="0.7",
        benchmark_track="agentic",
        locale="en-US",
        protocol_mode="control",
        matched_pair_id="trajectory-en-us-pair-001",
    )
    del scenario[missing_field]

    with pytest.raises(ValidationError, match=rf"missing fields:.*{missing_field}"):
        validate_scenario(scenario)


@pytest.mark.parametrize(
    ("prefill_messages", "message"),
    [
        (None, "requires exactly 2 or 4 prefill_messages"),
        (
            [
                {"role": "assistant", "content": "Wrong first role."},
                {"role": "user", "content": "Wrong second role."},
            ],
            "role must alternate",
        ),
        (
            [
                {"role": "user", "content": "First."},
                {"role": "assistant", "content": "Second."},
                {"role": "user", "content": "Third."},
            ],
            "requires exactly 2 or 4 prefill_messages",
        ),
    ],
)
def test_v07_prefill_stress_rejects_invalid_history(scenario_factory, prefill_messages, message):
    scenario = scenario_factory(
        benchmark_version="0.7",
        benchmark_track="agentic",
        locale="en-US",
        protocol_mode="prefill_stress",
        matched_pair_id="trajectory-en-us-pair-001",
    )
    if prefill_messages is not None:
        scenario["prefill_messages"] = prefill_messages

    with pytest.raises(ValidationError, match=message):
        validate_scenario(scenario)


@pytest.mark.parametrize("protocol_mode", ["continuous", "prefill_recovery"])
def test_v07_agentic_rejects_v05_protocol_modes(scenario_factory, protocol_mode):
    scenario = scenario_factory(
        benchmark_version="0.7",
        benchmark_track="agentic",
        locale="en-US",
        protocol_mode=protocol_mode,
        matched_pair_id="trajectory-en-us-pair-001",
    )

    with pytest.raises(ValidationError, match="protocol_mode"):
        validate_scenario(scenario)


def test_v07_constants_register_version_and_categories():
    assert "0.7" in SUPPORTED_BENCHMARK_VERSIONS
    assert V07_CATEGORIES == REGISTERED_V07_CATEGORIES


@pytest.mark.parametrize("version", ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6"])
@pytest.mark.parametrize("category", sorted(V07_CATEGORIES))
def test_legacy_versions_reject_v07_categories(scenario_factory, version, category):
    overrides = {"benchmark_version": version, "category": category}
    if version == "0.5":
        overrides.update(
            locale="en-US",
            protocol_mode="continuous",
            matched_pair_id="legacy-pair-001",
        )
    scenario = scenario_factory(**overrides)

    with pytest.raises(ValidationError, match="unknown category"):
        validate_scenario(scenario)
    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(SCHEMA).validate(scenario)


def test_json_schema_accepts_representative_version_contracts(scenario_factory):
    validator = Draft202012Validator(SCHEMA)
    scenarios = [
        scenario_factory(
            benchmark_version="0.5",
            locale="en-US",
            protocol_mode="continuous",
            matched_pair_id="legacy-pair-001",
        ),
        scenario_factory(benchmark_version="0.6"),
        scenario_factory(benchmark_version="0.7", benchmark_track="core"),
        scenario_factory(
            benchmark_version="0.7",
            benchmark_track="agentic",
            category="trajectory_recovery_and_correction",
            locale="en-US",
            protocol_mode="prefill_stress",
            matched_pair_id="trajectory-en-us-pair-001",
            prefill_messages=[
                {"role": "user", "content": "Synthetic prior request."},
                {"role": "assistant", "content": "Synthetic prior response."},
            ],
        ),
    ]

    for scenario in scenarios:
        validator.validate(scenario)


def test_json_schema_keeps_v05_protocol_modes_version_specific(scenario_factory):
    scenario = scenario_factory(
        benchmark_version="0.5",
        locale="en-US",
        protocol_mode="control",
        matched_pair_id="legacy-pair-001",
    )

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(SCHEMA).validate(scenario)


def test_json_schema_keeps_benchmark_track_v07_specific(scenario_factory):
    scenario = scenario_factory(
        benchmark_version="0.5",
        benchmark_track="core",
        locale="en-US",
        protocol_mode="continuous",
        matched_pair_id="legacy-pair-001",
    )

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(SCHEMA).validate(scenario)


def test_json_schema_rejects_v07_core_agentic_fields(scenario_factory):
    scenario = scenario_factory(
        benchmark_version="0.7",
        benchmark_track="core",
        locale="en-US",
    )

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(SCHEMA).validate(scenario)
