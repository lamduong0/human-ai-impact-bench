"""Derive digest-bound v0.7 evidence maturity without authorizing deployment."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.validation import ValidationError

_CONFIGURATION_FIELDS = {
    "index_version",
    "benchmark_version",
    "configuration_count",
    "scenario_count",
    "category_counts",
    "language_counts",
    "review_status_counts",
    "artifacts",
    "configurations",
}
_EVIDENCE_FIELDS = {
    "manifest_version",
    "configuration_sha256",
    "criteria_document_sha256",
    "criteria_registered_at",
    "candidate_families",
    "run_reports",
    "judge_sha256",
    "blind_set_verification",
    "human_calibration",
    "agreement_report_sha256",
    "agreement_passed",
    "discrimination_report_sha256",
    "discrimination_passed",
    "failure_counts",
    "failure_counts_report_digest",
    "earliest_result_at",
}
_REQUIRED_EVIDENCE_FIELDS = {"manifest_version", "configuration_sha256"}
_RUN_REPORT_FIELDS = {"candidate_family_id", "report_sha256", "result_at", "complete"}
_BLIND_FIELDS = {
    "valid",
    "scenario_count",
    "commitment_algorithm",
    "manifest_sha256",
}
_CALIBRATION_FIELDS = {
    "sample_sha256",
    "sample_size",
    "blinded",
    "double_rated",
    "stratified_by",
}
_FAILURE_FIELDS = {"failed_scenarios", "retry_count", "missing_results"}
_STRATA = {"category", "risk_level", "language", "protocol_mode"}
_REVIEWED_STATUSES = {"reviewed", "release_ready"}


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {path}") from exc
    except OSError as exc:
        raise ValidationError(f"could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a JSON object")
    return value


def _is_nonnegative_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _require_digest(value: Any, label: str) -> None:
    if not (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    ):
        raise ValidationError(f"{label} must be a lowercase SHA-256 digest")


def _utc_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a UTC timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValidationError(f"{label} must be a UTC timestamp") from exc


def _validate_counts(value: Any, label: str, total: int) -> None:
    if not isinstance(value, dict) or not value:
        raise ValidationError(f"{label} must be a non-empty object")
    if any(not isinstance(key, str) or not key for key in value):
        raise ValidationError(f"{label} keys must be non-empty strings")
    if any(not _is_nonnegative_integer(count) for count in value.values()):
        raise ValidationError(f"{label} values must be non-negative integers")
    if sum(value.values()) != total:
        raise ValidationError(f"{label} must sum to scenario_count")


def _validate_configuration_index(configuration: dict[str, Any]) -> None:
    if set(configuration) != _CONFIGURATION_FIELDS:
        raise ValidationError("configuration index has invalid fields")
    if configuration["index_version"] != "0.1" or configuration["benchmark_version"] != "0.7":
        raise ValidationError("configuration index must be the v0.7 index_version '0.1'")
    for field in ("configuration_count", "scenario_count"):
        if not _is_nonnegative_integer(configuration[field]):
            raise ValidationError(f"configuration index {field} must be a non-negative integer")
    if not isinstance(configuration["configurations"], dict):
        raise ValidationError("configuration index configurations must be an object")
    if configuration["configuration_count"] != len(configuration["configurations"]):
        raise ValidationError("configuration_count does not match configurations")
    _validate_counts(
        configuration["review_status_counts"],
        "configuration index review_status_counts",
        configuration["scenario_count"],
    )
    review_counts: Counter[str] = Counter()
    scenario_count = 0
    for name, item in configuration["configurations"].items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(item, dict)
            or "scenario_count" not in item
            or "review_status_counts" not in item
            or not _is_nonnegative_integer(item["scenario_count"])
        ):
            raise ValidationError("configuration index has an invalid configuration summary")
        _validate_counts(
            item["review_status_counts"],
            f"configuration {name} review_status_counts",
            item["scenario_count"],
        )
        scenario_count += item["scenario_count"]
        review_counts.update(item["review_status_counts"])
    if scenario_count != configuration["scenario_count"]:
        raise ValidationError("configuration summaries do not match scenario_count")
    if dict(sorted(review_counts.items())) != configuration["review_status_counts"]:
        raise ValidationError("configuration index review summary does not match configurations")


def _reviews_are_complete(configuration: dict[str, Any]) -> bool:
    counts = configuration["review_status_counts"]
    return bool(counts) and set(counts) <= _REVIEWED_STATUSES


def _validate_evidence(
    evidence: dict[str, Any], configuration: dict[str, Any]
) -> tuple[bool, bool]:
    if not _REQUIRED_EVIDENCE_FIELDS <= set(evidence) or set(evidence) - _EVIDENCE_FIELDS:
        raise ValidationError("evaluation-evidence manifest has invalid fields")
    if evidence["manifest_version"] != "0.1":
        raise ValidationError("evaluation-evidence manifest_version must be '0.1'")

    for field in (
        "configuration_sha256",
        "criteria_document_sha256",
        "judge_sha256",
        "agreement_report_sha256",
        "discrimination_report_sha256",
        "failure_counts_report_digest",
    ):
        if field in evidence:
            _require_digest(evidence[field], f"evaluation-evidence {field}")
    if evidence["configuration_sha256"] != record_digest(configuration):
        raise ValidationError("evaluation-evidence configuration digest does not match index")
    for field in ("agreement_passed", "discrimination_passed"):
        if field in evidence and not isinstance(evidence[field], bool):
            raise ValidationError(f"evaluation-evidence {field} must be a boolean")

    families = evidence.get("candidate_families")
    if families is not None:
        if (
            not isinstance(families, list)
            or len(families) < 3
            or any(not isinstance(family, str) or not family.strip() for family in families)
            or len(set(families)) != len(families)
        ):
            raise ValidationError(
                "validated evaluation requires at least three distinct candidate families"
            )

    reports = evidence.get("run_reports")
    report_families: set[str] = set()
    report_digests: set[str] = set()
    result_times: list[datetime] = []
    if reports is not None:
        if not isinstance(reports, list) or not reports:
            raise ValidationError("evaluation-evidence run_reports must be a non-empty array")
        for index, report in enumerate(reports):
            label = f"evaluation-evidence run_reports[{index}]"
            if not isinstance(report, dict) or set(report) != _RUN_REPORT_FIELDS:
                raise ValidationError(f"{label} has invalid fields")
            family = report["candidate_family_id"]
            if not isinstance(family, str) or not family.strip():
                raise ValidationError(f"{label}.candidate_family_id must be a non-empty string")
            _require_digest(report["report_sha256"], f"{label}.report_sha256")
            if report["report_sha256"] in report_digests:
                raise ValidationError("evaluation-evidence run-report digests must be unique")
            if not isinstance(report["complete"], bool):
                raise ValidationError(f"{label}.complete must be a boolean")
            report_families.add(family)
            report_digests.add(report["report_sha256"])
            result_times.append(_utc_timestamp(report["result_at"], f"{label}.result_at"))
        if families is not None and not report_families <= set(families):
            raise ValidationError(
                "evaluation-evidence run report has an undeclared candidate family"
            )

    registered_at = None
    if "criteria_registered_at" in evidence:
        registered_at = _utc_timestamp(
            evidence["criteria_registered_at"], "evaluation-evidence criteria_registered_at"
        )
    if "earliest_result_at" in evidence:
        earliest_result = _utc_timestamp(
            evidence["earliest_result_at"], "evaluation-evidence earliest_result_at"
        )
        if result_times and earliest_result != min(result_times):
            raise ValidationError(
                "evaluation-evidence earliest_result_at does not match bound results"
            )
    if registered_at is not None and any(registered_at >= value for value in result_times):
        raise ValidationError("evaluation criteria must be registered before all bound results")

    blind = evidence.get("blind_set_verification")
    if blind is not None:
        if not isinstance(blind, dict) or set(blind) != _BLIND_FIELDS:
            raise ValidationError("evaluation-evidence blind_set_verification has invalid fields")
        _require_digest(blind["manifest_sha256"], "blind-set manifest_sha256")
        if not isinstance(blind["valid"], bool):
            raise ValidationError("blind-set valid must be a boolean")
        if not _is_nonnegative_integer(blind["scenario_count"]) or blind["scenario_count"] == 0:
            raise ValidationError("blind-set scenario_count must be a positive integer")
        if blind["commitment_algorithm"] != "sha256-canonical-json-v1":
            raise ValidationError("blind-set commitment algorithm is not supported")

    calibration = evidence.get("human_calibration")
    if calibration is not None:
        if not isinstance(calibration, dict) or set(calibration) != _CALIBRATION_FIELDS:
            raise ValidationError("evaluation-evidence human_calibration has invalid fields")
        _require_digest(calibration["sample_sha256"], "human calibration sample_sha256")
        if (
            not _is_nonnegative_integer(calibration["sample_size"])
            or calibration["sample_size"] == 0
            or (blind is not None and calibration["sample_size"] > blind["scenario_count"])
        ):
            raise ValidationError("human calibration sample_size is invalid")
        if not isinstance(calibration["blinded"], bool) or not isinstance(
            calibration["double_rated"], bool
        ):
            raise ValidationError("human calibration result fields must be booleans")
        strata = calibration["stratified_by"]
        if (
            not isinstance(strata, list)
            or any(not isinstance(stratum, str) for stratum in strata)
            or len(strata) != len(set(strata))
            or set(strata) != _STRATA
        ):
            raise ValidationError(
                "human calibration must be stratified by category, risk, language, and protocol"
            )

    failures = evidence.get("failure_counts")
    if failures is not None:
        if not isinstance(failures, dict) or set(failures) != _FAILURE_FIELDS:
            raise ValidationError("evaluation-evidence failure_counts has invalid fields")
        if any(not _is_nonnegative_integer(value) for value in failures.values()):
            raise ValidationError(
                "evaluation-evidence failure counts must be non-negative integers"
            )

    discrimination_fields = {
        "criteria_document_sha256",
        "criteria_registered_at",
        "candidate_families",
        "run_reports",
        "judge_sha256",
        "discrimination_report_sha256",
        "discrimination_passed",
        "failure_counts",
        "failure_counts_report_digest",
        "earliest_result_at",
    }
    discrimination_complete = (
        discrimination_fields <= set(evidence)
        and report_families == set(families)
        and all(report["complete"] for report in reports)
        and evidence["discrimination_passed"] is True
        and failures["failed_scenarios"] == 0
        and failures["missing_results"] == 0
    )
    human_fields = {
        "blind_set_verification",
        "human_calibration",
        "agreement_report_sha256",
        "agreement_passed",
    }
    human_complete = (
        human_fields <= set(evidence)
        and blind["valid"] is True
        and calibration["blinded"] is True
        and calibration["double_rated"] is True
        and evidence["agreement_passed"] is True
    )
    return discrimination_complete, human_complete


def evaluate_evidence_status(
    configuration_index_path: Path,
    evidence_path: Path | None = None,
) -> dict[str, Any]:
    """Return v0.7 evidence maturity; no evidence state can authorize deployment."""
    configuration = _load_json(Path(configuration_index_path), "configuration index")
    _validate_configuration_index(configuration)
    configuration_sha256 = record_digest(configuration)

    if evidence_path is not None:
        evidence = _load_json(Path(evidence_path), "evaluation-evidence manifest")
        discrimination_complete, human_complete = _validate_evidence(evidence, configuration)
    else:
        discrimination_complete = human_complete = False

    reviewed = _reviews_are_complete(configuration)
    missing = []
    if not reviewed:
        missing.append("independent_review")
    if not discrimination_complete:
        missing.append("preregistered_discrimination")
    if not human_complete:
        missing.append("blind_human_calibration")
    stage = (
        "PREVIEW" if not reviewed else "VALIDATED_EVALUATION" if not missing else "REVIEWED_DATASET"
    )

    return {
        "evidence_stage": stage,
        "deployment_action": "HOLD",
        "missing_evidence": missing,
        "configuration_sha256": configuration_sha256,
    }
