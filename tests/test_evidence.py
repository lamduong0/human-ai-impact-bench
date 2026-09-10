from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.evidence import evaluate_evidence_status
from humanai_impact_bench.validation import ValidationError
from scripts.generate_v07_review_manifests import build_manifest

_DIGEST = "a" * 64


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _configuration_index(*, reviewed: bool, root: Path | None = None) -> dict[str, Any]:
    status = "reviewed" if reviewed else "draft_unreviewed"
    index = {
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
    if root is not None:
        directory = root / "core/en"
        directory.mkdir(parents=True, exist_ok=True)
        records = [
            {
                "benchmark_version": "0.7",
                "benchmark_track": "core",
                "scenario_id": f"evidence-source-{i}",
                "language": "en",
                "title": f"Synthetic evidence fixture {i}",
                "category": "dependency_boundaries",
                "risk_level": "low",
                "context": "A fictional adult asks for bounded assistance.",
                "persona": {
                    "age_group": "adult",
                    "situation": "Synthetic test",
                    "communication_style": "Direct",
                },
                "initial_prompt": f"Help me consider this choice {i}.",
                "follow_up_prompts": ["I will make the decision."],
                "expected_behaviors": ["Supports the user's decision."],
                "failure_modes": ["Takes control of the decision."],
                "dimensions": ["autonomy_support"],
                "tags": [
                    f"concept-family-test-{i}",
                    f"context-test-{i}",
                    "derivation-authored-new",
                ],
            }
            for i in range(3)
        ]
        source = directory / "dependency_boundaries.jsonl"
        source.write_text("".join(json.dumps(record) + "\n" for record in records))
        manifest = build_manifest(directory, "core", "en")
        if reviewed:
            for record in records:
                item = manifest["items"][record["scenario_id"]]
                item["author_ids"] = ["fixture-author"]
                item["review_events"] = [
                    {
                        "review_type": "construct",
                        "reviewer_id": "fixture-reviewer",
                        "qualification": "Declared fixture qualification",
                        "decision": "approved",
                        "reviewed_at": "2026-09-05T00:00:00Z",
                        "conflict_disclosure": "none",
                        "reviewed_locale": "en-US",
                        "notes": "Synthetic test, not corpus review.",
                        "scenario_digest": record_digest(record),
                    }
                ]
                item["status"] = "reviewed"
        review_path = _write_json(directory / "review-status.json", manifest)
        summary = index["configurations"]["v0.7-core-en"]
        summary["files"][0]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        summary["review_manifest"]["sha256"] = hashlib.sha256(review_path.read_bytes()).hexdigest()
    return index


def _complete_evidence_manifest(configuration: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    candidate_families = overrides.pop("candidate_families", ["family-a", "family-b", "family-c"])
    earliest_result_at = overrides.pop("earliest_result_at", "2026-09-07T00:00:00Z")
    manifest = {
        "manifest_version": "0.1",
        "configuration_name": "v0.7-core-en",
        "configuration_sha256": record_digest(configuration["configurations"]["v0.7-core-en"]),
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
        "agreement_passed": True,
        "discrimination_report_sha256": "1" * 64,
        "discrimination_passed": True,
        "failure_counts": {
            "failed_scenarios": 0,
            "retry_count": 0,
            "missing_results": 0,
        },
        "failure_counts_report_digest": "2" * 64,
        "earliest_result_at": earliest_result_at,
    }
    manifest.update(overrides)
    return manifest


def test_draft_configuration_is_preview_and_hold(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=False, root=tmp_path)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)

    result = evaluate_evidence_status(configuration_path)

    assert result["evidence_stage"] == "PREVIEW"
    assert result["deployment_action"] == "HOLD"
    assert result["missing_evidence"] == [
        "independent_review",
        "preregistered_discrimination",
        "blind_human_calibration",
        "quantitative_artifact_verification_not_implemented",
    ]


def test_reviewed_configuration_without_evaluation_evidence_stays_hold(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True, root=tmp_path)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)

    result = evaluate_evidence_status(configuration_path)

    assert result == {
        "configuration_name": "v0.7-core-en",
        "benchmark_track": "core",
        "language": "en",
        "evidence_stage": "REVIEWED_DATASET",
        "deployment_action": "HOLD",
        "missing_evidence": [
            "preregistered_discrimination",
            "blind_human_calibration",
            "quantitative_artifact_verification_not_implemented",
        ],
        "configuration_sha256": record_digest(configuration["configurations"]["v0.7-core-en"]),
    }


def test_configuration_review_summary_cannot_manufacture_review(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=False, root=tmp_path)
    configuration["review_status_counts"] = {"reviewed": 3}
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)

    with pytest.raises(ValidationError, match="review summary"):
        evaluate_evidence_status(configuration_path)


def test_asserted_empirical_evidence_never_promotes_without_verification(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True, root=tmp_path)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence_path = _write_json(
        tmp_path / "evaluation-evidence.json",
        _complete_evidence_manifest(configuration),
    )

    result = evaluate_evidence_status(configuration_path, evidence_path)

    assert result == {
        "configuration_name": "v0.7-core-en",
        "benchmark_track": "core",
        "language": "en",
        "evidence_stage": "REVIEWED_DATASET",
        "deployment_action": "HOLD",
        "missing_evidence": [
            "preregistered_discrimination",
            "blind_human_calibration",
            "quantitative_artifact_verification_not_implemented",
        ],
        "configuration_sha256": record_digest(configuration["configurations"]["v0.7-core-en"]),
    }


@pytest.mark.parametrize(
    ("result_field", "missing_evidence"),
    [
        ("agreement_passed", ["blind_human_calibration"]),
        ("discrimination_passed", ["preregistered_discrimination"]),
    ],
)
def test_failed_evidence_report_cannot_promote_evaluation(
    tmp_path: Path,
    result_field: str,
    missing_evidence: list[str],
) -> None:
    configuration = _configuration_index(reviewed=True, root=tmp_path)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence = _complete_evidence_manifest(configuration)
    evidence[result_field] = False
    evidence_path = _write_json(tmp_path / "evaluation-evidence.json", evidence)

    result = evaluate_evidence_status(configuration_path, evidence_path)

    assert result["evidence_stage"] == "REVIEWED_DATASET"
    assert set(missing_evidence) <= set(result["missing_evidence"])
    assert result["missing_evidence"] == [
        "preregistered_discrimination",
        "blind_human_calibration",
        "quantitative_artifact_verification_not_implemented",
    ]
    assert result["deployment_action"] == "HOLD"


@pytest.mark.parametrize(
    ("reviewed", "stage", "missing_evidence"),
    [
        (
            False,
            "PREVIEW",
            [
                "independent_review",
                "preregistered_discrimination",
                "blind_human_calibration",
            ],
        ),
        (
            True,
            "REVIEWED_DATASET",
            ["preregistered_discrimination", "blind_human_calibration"],
        ),
    ],
)
def test_partial_valid_evidence_returns_review_derived_lower_stage(
    tmp_path: Path,
    reviewed: bool,
    stage: str,
    missing_evidence: list[str],
) -> None:
    configuration = _configuration_index(reviewed=reviewed, root=tmp_path)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence_path = _write_json(
        tmp_path / "evaluation-evidence.json",
        {
            "manifest_version": "0.1",
            "configuration_name": "v0.7-core-en",
            "configuration_sha256": record_digest(configuration["configurations"]["v0.7-core-en"]),
        },
    )

    result = evaluate_evidence_status(configuration_path, evidence_path)

    assert result["evidence_stage"] == stage
    assert result["missing_evidence"] == missing_evidence + [
        "quantitative_artifact_verification_not_implemented"
    ]
    assert result["deployment_action"] == "HOLD"


def test_missing_failure_counts_report_digest_blocks_promotion(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True, root=tmp_path)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence = _complete_evidence_manifest(configuration)
    del evidence["failure_counts_report_digest"]
    evidence_path = _write_json(tmp_path / "evaluation-evidence.json", evidence)

    result = evaluate_evidence_status(configuration_path, evidence_path)

    assert result["evidence_stage"] == "REVIEWED_DATASET"
    assert result["missing_evidence"] == [
        "preregistered_discrimination",
        "blind_human_calibration",
        "quantitative_artifact_verification_not_implemented",
    ]


def test_invalid_failure_counts_report_digest_is_rejected(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True, root=tmp_path)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence = _complete_evidence_manifest(configuration)
    evidence["failure_counts_report_digest"] = "not-a-digest"
    evidence_path = _write_json(tmp_path / "evaluation-evidence.json", evidence)

    with pytest.raises(ValidationError, match="failure_counts_report_digest"):
        evaluate_evidence_status(configuration_path, evidence_path)


def test_validated_evaluation_requires_three_candidate_families(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True, root=tmp_path)
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
    configuration = _configuration_index(reviewed=True, root=tmp_path)
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
    configuration = _configuration_index(reviewed=True, root=tmp_path)
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
    configuration = _configuration_index(reviewed=True, root=tmp_path)
    configuration_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence = _complete_evidence_manifest(configuration)
    evidence["configuration_sha256"] = "0" * 64
    evidence_path = _write_json(tmp_path / "evaluation-evidence.json", evidence)

    with pytest.raises(ValidationError, match="configuration digest"):
        evaluate_evidence_status(configuration_path, evidence_path)


def test_human_calibration_rejects_malformed_strata(tmp_path: Path) -> None:
    configuration = _configuration_index(reviewed=True, root=tmp_path)
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
    configuration = _configuration_index(reviewed=True, root=tmp_path)
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


def test_two_json_files_with_invented_hashes_cannot_manufacture_evidence(tmp_path):
    configuration = _configuration_index(reviewed=True)
    evidence = _complete_evidence_manifest(configuration)
    # Reproduce the original accepted format exactly, with no real source,
    # review, run, calibration or criteria artifact anywhere in the directory.
    evidence.pop("configuration_name")
    evidence["configuration_sha256"] = record_digest(configuration)
    index_path = _write_json(tmp_path / "configuration-index.json", configuration)
    evidence_path = _write_json(tmp_path / "evaluation-evidence.json", evidence)
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "configuration-index.json",
        "evaluation-evidence.json",
    ]
    with pytest.raises(ValidationError, match="artifact|file not found"):
        evaluate_evidence_status(index_path, evidence_path)


@pytest.mark.parametrize(
    "defect", ["source_bytes", "review_bytes", "review_claim", "unlisted_source", "wrong_counts"]
)
def test_reviewed_stage_verifies_referenced_bytes_and_review_evidence(tmp_path, defect):
    configuration = _configuration_index(reviewed=True, root=tmp_path)
    summary = configuration["configurations"]["v0.7-core-en"]
    source = tmp_path / summary["files"][0]["path"]
    review_path = tmp_path / summary["review_manifest"]["path"]
    if defect == "source_bytes":
        source.write_text(source.read_text().replace("choice 0", "revised choice 0"))
    elif defect == "review_bytes":
        review_path.write_text(review_path.read_text() + "\n")
    elif defect == "review_claim":
        manifest = json.loads(review_path.read_text())
        for item in manifest["items"].values():
            item["review_events"] = []
        _write_json(review_path, manifest)
        summary["review_manifest"]["sha256"] = hashlib.sha256(review_path.read_bytes()).hexdigest()
    elif defect == "unlisted_source":
        (source.parent / "extra.jsonl").write_text(source.read_text())
    else:
        summary["category_counts"] = {"grief_and_loss": 3}
        configuration["category_counts"] = {"grief_and_loss": 3}
    path = _write_json(tmp_path / "index.json", configuration)
    with pytest.raises(ValidationError):
        evaluate_evidence_status(path)


def _with_draft_vietnamese(configuration, root):
    index = deepcopy(configuration)
    english = index["configurations"]["v0.7-core-en"]
    directory = root / "core/vi"
    directory.mkdir(parents=True)
    records = [
        json.loads(line) for line in (root / english["files"][0]["path"]).read_text().splitlines()
    ]
    for record in records:
        record["language"] = "vi"
        record["tags"].append("requires-cultural-review")
    source = directory / "dependency_boundaries.jsonl"
    source.write_text("".join(json.dumps(record) + "\n" for record in records))
    manifest = build_manifest(directory, "core", "vi")
    review = _write_json(directory / "review-status.json", manifest)
    summary = deepcopy(english)
    summary.update(
        language="vi", language_counts={"vi": 3}, review_status_counts={"draft_unreviewed": 3}
    )
    summary["files"] = [
        {
            "path": "core/vi/dependency_boundaries.jsonl",
            "scenario_count": 3,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
    ]
    summary["review_manifest"] = {
        "path": "core/vi/review-status.json",
        "sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
    }
    index["configurations"]["v0.7-core-vi-preview"] = summary
    index.update(
        configuration_count=2,
        scenario_count=6,
        category_counts={"dependency_boundaries": 6},
        language_counts={"en": 3, "vi": 3},
        review_status_counts={"draft_unreviewed": 3, "reviewed": 3},
    )
    return index


def test_maturity_is_per_configuration_and_vi_does_not_downgrade_en(tmp_path):
    index = _with_draft_vietnamese(_configuration_index(reviewed=True, root=tmp_path), tmp_path)
    path = _write_json(tmp_path / "index.json", index)
    result = evaluate_evidence_status(path)
    assert "evidence_stage" not in result  # There is no combined instrument maturity.
    assert result["configurations"]["v0.7-core-en"]["evidence_stage"] == "REVIEWED_DATASET"
    assert result["configurations"]["v0.7-core-vi-preview"]["evidence_stage"] == "PREVIEW"
    index["configurations"]["v0.7-core-vi-preview"]["review_manifest"]["path"] = (
        "core/vi/missing.json"
    )
    _write_json(path, index)
    selected = evaluate_evidence_status(path, configuration_name="v0.7-core-en")
    assert selected["evidence_stage"] == "REVIEWED_DATASET"


def test_selected_evidence_binds_its_configuration_not_unrelated_vi_changes(tmp_path):
    index = _with_draft_vietnamese(_configuration_index(reviewed=True, root=tmp_path), tmp_path)
    evidence = _complete_evidence_manifest(index)
    path = _write_json(tmp_path / "index.json", index)
    evidence_path = _write_json(tmp_path / "evidence.json", evidence)
    result = evaluate_evidence_status(path, evidence_path, configuration_name="v0.7-core-en")
    assert result["evidence_stage"] == "REVIEWED_DATASET"
    with pytest.raises(ValidationError, match="configuration"):
        evaluate_evidence_status(path, evidence_path, configuration_name="v0.7-core-vi-preview")


def test_cli_selects_one_verified_configuration(tmp_path, capsys):
    from humanai_impact_bench.cli import main

    index = _with_draft_vietnamese(_configuration_index(reviewed=True, root=tmp_path), tmp_path)
    path = _write_json(tmp_path / "index.json", index)
    assert (
        main(
            [
                "evidence-status",
                "--configuration-index",
                str(path),
                "--configuration",
                "v0.7-core-en",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["configuration_name"] == "v0.7-core-en"
    assert result["evidence_stage"] == "REVIEWED_DATASET"
    assert result["deployment_action"] == "HOLD"


def test_configuration_track_type_fails_closed_without_an_uncaught_type_error(tmp_path):
    index = _configuration_index(reviewed=True, root=tmp_path)
    index["configurations"]["v0.7-core-en"]["benchmark_track"] = []
    path = _write_json(tmp_path / "index.json", index)
    with pytest.raises(ValidationError, match="track"):
        evaluate_evidence_status(path)


@pytest.mark.parametrize("field", ["category_counts", "language_counts"])
def test_index_aggregate_counts_cannot_misstate_its_configuration_summaries(tmp_path, field):
    index = _configuration_index(reviewed=True, root=tmp_path)
    index[field] = {"grief_and_loss": 3} if field == "category_counts" else {"vi": 3}
    path = _write_json(tmp_path / "index.json", index)
    with pytest.raises(ValidationError, match="summary"):
        evaluate_evidence_status(path)


@pytest.mark.parametrize("timestamp", ["2026-9-6T00:00:00Z", "2026-09-06T00:00:00.1Z"])
def test_evidence_timestamps_follow_review_timestamp_precision(tmp_path, timestamp):
    from jsonschema import FormatChecker
    from jsonschema.exceptions import ValidationError as SchemaError

    index = _configuration_index(reviewed=True, root=tmp_path)
    evidence = _complete_evidence_manifest(index, criteria_registered_at=timestamp)
    path = _write_json(tmp_path / "index.json", index)
    evidence_path = _write_json(tmp_path / "evidence.json", evidence)
    with pytest.raises(ValidationError, match="UTC timestamp"):
        evaluate_evidence_status(path, evidence_path)
    schema = json.loads(
        (Path(__file__).parents[1] / "schemas/evaluation-evidence.schema.json").read_text()
    )
    with pytest.raises(SchemaError):
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(evidence)
