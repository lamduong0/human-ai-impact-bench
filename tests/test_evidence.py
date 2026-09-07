from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.evidence import evaluate_evidence_status
from humanai_impact_bench.validation import ValidationError

_DIGEST = "a" * 64


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _configuration_index(*, reviewed: bool) -> dict[str, Any]:
    status = "reviewed" if reviewed else "draft_unreviewed"
    return {
        "index_version": "0.1",
        "benchmark_version": "0.7",
        "configuration_count": 1,
        "scenario_count": 3,
        "category_counts": {"dependency_boundaries": 3},
        "language_counts": {"en": 3},
        "review_status_counts": {status: 3},
        "artifacts": {
            "lineage": {"path": "lineage-index.json", "sha256": _DIGEST},
            "overlap": {"path": "overlap-audit.json", "sha256": _DIGEST},
            "split": {"path": "split-index.json", "sha256": _DIGEST},
        },
        "configurations": {
            "v0.7-core-en": {
                "benchmark_track": "core",
                "language": "en",
                "scenario_count": 3,
                "category_counts": {"dependency_boundaries": 3},
                "language_counts": {"en": 3},
                "review_status_counts": {status: 3},
                "files": [
                    {
                        "path": "core/en/dependency_boundaries.jsonl",
                        "scenario_count": 3,
                        "sha256": _DIGEST,
                    }
                ],
                "review_manifest": {
                    "path": "core/en/review-status.json",
                    "sha256": _DIGEST,
                },
            }
        },
    }


def _complete_evidence_manifest(configuration: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    candidate_families = overrides.pop("candidate_families", ["family-a", "family-b", "family-c"])
    earliest_result_at = overrides.pop("earliest_result_at", "2026-09-07T00:00:00Z")
    manifest = {
        "manifest_version": "0.1",
        "configuration_sha256": record_digest(configuration),
        "criteria_document_sha256": "b" * 64,
        "criteria_registered_at": "2026-09-06T00:00:00Z",
        "candidate_families": candidate_families,
        "run_reports": [
            {
                "candidate_family_id": family,
                "report_sha256": f"{index + 1:x}" * 64,
                "result_at": earliest_result_at,
                "complete": True,
            }
            for index, family in enumerate(candidate_families)
        ],
        "judge_sha256": "c" * 64,
        "blind_set_verification": {
            "valid": True,
            "scenario_count": 3,
            "commitment_algorithm": "sha256-canonical-json-v1",
            "manifest_sha256": "d" * 64,
        },
        "human_calibration": {
            "sample_sha256": "e" * 64,
            "sample_size": 3,
            "blinded": True,
            "double_rated": True,
            "stratified_by": ["category", "risk_level", "language", "protocol_mode"],
        },
        "agreement_report_sha256": "f" * 64,
        "discrimination_report_sha256": "1" * 64,
        "failure_counts": {
            "failed_scenarios": 0,
            "retry_count": 0,
            "missing_results": 0,
        },
        "earliest_result_at": earliest_result_at,
    }
    manifest.update(overrides)
    return manifest


def test_draft_configuration_is_preview_and_hold(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=False)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)

    result = evaluate_evidence_status(configuration_path)

    assert result["evidence_stage"] == "PREVIEW"
    assert result["deployment_action"] == "HOLD"
    assert result["missing_evidence"] == [
        "independent_review",
        "preregistered_discrimination",
        "blind_human_calibration",
    ]


def test_reviewed_configuration_without_evaluation_evidence_stays_hold(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)

    result = evaluate_evidence_status(configuration_path)

    assert result == {
        "evidence_stage": "REVIEWED_DATASET",
        "deployment_action": "HOLD",
        "missing_evidence": ["preregistered_discrimination", "blind_human_calibration"],
        "configuration_sha256": record_digest(configuration),
    }


def test_configuration_review_summary_cannot_manufacture_review(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=False)
    configuration["review_status_counts"] = {"reviewed": 3}
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)

    with pytest.raises(ValidationError, match="review summary"):
        evaluate_evidence_status(configuration_path)


def test_complete_evidence_reaches_validated_evaluation_but_not_allow(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence_path = _write_json(
        tmp_path / "evaluation-evidence.json",
        _complete_evidence_manifest(configuration),
    )

    result = evaluate_evidence_status(configuration_path, evidence_path)

    assert result == {
        "evidence_stage": "VALIDATED_EVALUATION",
        "deployment_action": "HOLD",
        "missing_evidence": [],
        "configuration_sha256": record_digest(configuration),
    }


def test_validated_evaluation_requires_three_candidate_families(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence_path = _write_json(
        tmp_path / "evaluation-evidence.json",
        _complete_evidence_manifest(
            configuration,
            candidate_families=["family-a", "family-b"],
        ),
    )

    with pytest.raises(ValidationError, match="at least three distinct candidate families"):
        evaluate_evidence_status(configuration_path, evidence_path)


def test_candidate_family_validation_rejects_non_string_values(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence_path = _write_json(
        tmp_path / "evaluation-evidence.json",
        _complete_evidence_manifest(
            configuration,
            candidate_families=["family-a", "family-b", {"family": "c"}],
        ),
    )

    with pytest.raises(ValidationError, match="at least three distinct candidate families"):
        evaluate_evidence_status(configuration_path, evidence_path)


def test_criteria_must_predate_bound_results(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence_path = _write_json(
        tmp_path / "evaluation-evidence.json",
        _complete_evidence_manifest(
            configuration,
            criteria_registered_at="2026-09-08T00:00:00Z",
            earliest_result_at="2026-09-07T00:00:00Z",
        ),
    )

    with pytest.raises(ValidationError, match="criteria.*before.*results"):
        evaluate_evidence_status(configuration_path, evidence_path)


def test_evidence_is_bound_to_the_exact_configuration(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence = _complete_evidence_manifest(configuration)
    evidence["configuration_sha256"] = "0" * 64
    evidence_path = _write_json(tmp_path / "evaluation-evidence.json", evidence)

    with pytest.raises(ValidationError, match="configuration digest"):
        evaluate_evidence_status(configuration_path, evidence_path)


def test_human_calibration_rejects_malformed_strata(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence = _complete_evidence_manifest(configuration)
    evidence["human_calibration"]["stratified_by"] = [
        "category",
        "risk_level",
        "language",
        {"field": "protocol_mode"},
    ]
    evidence_path = _write_json(tmp_path / "evaluation-evidence.json", evidence)

    with pytest.raises(ValidationError, match="must be stratified"):
        evaluate_evidence_status(configuration_path, evidence_path)


def test_evidence_schema_accepts_contract_and_rejects_unknown_fields(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True)
    schema = json.loads(
        (Path(__file__).parents[1] / "schemas" / "evaluation-evidence.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema)
    evidence = _complete_evidence_manifest(configuration)

    validator.validate(evidence)
    evidence["unsupported_claim"] = "ALLOW"

    assert any(
        error.validator == "additionalProperties" for error in validator.iter_errors(evidence)
    )
