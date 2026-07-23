"""JSONL loading and deterministic validation for benchmark artifacts."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from humanai_impact_bench.constants import (
    CATEGORIES,
    CRITICAL_FAILURE_PENALTIES,
    DIMENSION_WEIGHTS,
    RISK_LEVELS,
    SUPPORTED_BENCHMARK_VERSIONS,
)

_SCENARIO_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SCENARIO_FIELDS = {
    "benchmark_version",
    "scenario_id",
    "language",
    "title",
    "category",
    "risk_level",
    "context",
    "persona",
    "initial_prompt",
    "follow_up_prompts",
    "expected_behaviors",
    "failure_modes",
    "dimensions",
    "tags",
}
_PERSONA_FIELDS = {
    "age_group",
    "situation",
    "communication_style",
    "vulnerability_factors",
}


class ValidationError(ValueError):
    """Raised when an artifact does not conform to the benchmark contract."""


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    records: list[dict[str, Any]] = []
    try:
        with source.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValidationError(
                        f"{source}:{line_number}: invalid JSON: {exc.msg}"
                    ) from exc
                if not isinstance(record, dict):
                    raise ValidationError(f"{source}:{line_number}: expected a JSON object")
                if "_source_line" in record:
                    raise ValidationError(
                        f"{source}:{line_number}: reserved field '_source_line' is not allowed"
                    )
                record["_source_line"] = line_number
                records.append(record)
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {source}") from exc
    except OSError as exc:
        raise ValidationError(f"could not read {source}: {exc}") from exc
    if not records:
        raise ValidationError(f"{source}: no records found")
    return records


def _require(record: dict[str, Any], fields: set[str], label: str) -> None:
    missing = sorted(field for field in fields if field not in record)
    if missing:
        raise ValidationError(f"{label}: missing fields: {', '.join(missing)}")


def _require_string(
    record: dict[str, Any],
    field: str,
    label: str,
    *,
    min_length: int = 1,
) -> None:
    value = record[field]
    if not isinstance(value, str) or len(value) < min_length:
        raise ValidationError(
            f"{label}: {field} must be a string with at least {min_length} character(s)"
        )


def _validate_string_array(
    value: Any,
    field: str,
    label: str,
    *,
    non_empty: bool,
    min_item_length: int = 1,
    unique: bool = False,
) -> None:
    if not isinstance(value, list) or (non_empty and not value):
        expected = "a non-empty array" if non_empty else "an array"
        raise ValidationError(f"{label}: {field} must be {expected}")
    if any(not isinstance(item, str) or len(item) < min_item_length for item in value):
        raise ValidationError(
            f"{label}: {field} items must be strings with at least {min_item_length} character(s)"
        )
    if unique and len(value) != len(set(value)):
        raise ValidationError(f"{label}: {field} items must be unique")


def validate_scenario(record: dict[str, Any]) -> None:
    line = record.get("_source_line", "?")
    label = f"scenario at line {line}"
    _require(
        record,
        _SCENARIO_FIELDS,
        label,
    )
    unexpected = sorted(set(record) - _SCENARIO_FIELDS - {"_source_line"})
    if unexpected:
        raise ValidationError(f"{label}: unexpected fields: {', '.join(unexpected)}")
    if record["benchmark_version"] not in SUPPORTED_BENCHMARK_VERSIONS:
        supported = ", ".join(repr(version) for version in sorted(SUPPORTED_BENCHMARK_VERSIONS))
        raise ValidationError(f"{label}: benchmark_version must be one of {supported}")
    for field in ("scenario_id", "language", "category", "risk_level"):
        _require_string(record, field, label)
    if not _SCENARIO_ID_PATTERN.fullmatch(record["scenario_id"]):
        raise ValidationError(f"{label}: scenario_id has an invalid format")
    _require_string(record, "title", label, min_length=3)
    _require_string(record, "context", label, min_length=10)
    _require_string(record, "initial_prompt", label, min_length=2)
    if record["category"] not in CATEGORIES:
        raise ValidationError(f"{label}: unknown category {record['category']!r}")
    if record["risk_level"] not in RISK_LEVELS:
        raise ValidationError(f"{label}: unknown risk level {record['risk_level']!r}")
    if record["language"] not in {"en", "vi"}:
        raise ValidationError(f"{label}: language must be 'en' or 'vi'")
    if not isinstance(record["persona"], dict):
        raise ValidationError(f"{label}: persona must be an object")
    persona = record["persona"]
    _require(persona, {"age_group", "situation", "communication_style"}, f"{label} persona")
    unexpected_persona = sorted(set(persona) - _PERSONA_FIELDS)
    if unexpected_persona:
        raise ValidationError(
            f"{label}: unexpected persona fields: {', '.join(unexpected_persona)}"
        )
    for field in ("age_group", "situation", "communication_style"):
        _require_string(persona, field, f"{label} persona")
    if "vulnerability_factors" in persona:
        _validate_string_array(
            persona["vulnerability_factors"],
            "vulnerability_factors",
            f"{label} persona",
            non_empty=False,
            unique=True,
        )
    _validate_string_array(
        record["follow_up_prompts"],
        "follow_up_prompts",
        label,
        non_empty=True,
        min_item_length=2,
    )
    for field in ("expected_behaviors", "failure_modes"):
        _validate_string_array(record[field], field, label, non_empty=True)
    _validate_string_array(record["dimensions"], "dimensions", label, non_empty=True, unique=True)
    unknown_dimensions = sorted(set(record["dimensions"]) - set(DIMENSION_WEIGHTS))
    if unknown_dimensions:
        raise ValidationError(f"{label}: unknown dimensions: {', '.join(unknown_dimensions)}")
    _validate_string_array(record["tags"], "tags", label, non_empty=False, unique=True)


def validate_annotation(record: dict[str, Any]) -> None:
    line = record.get("_source_line", "?")
    label = f"annotation at line {line}"
    _require(
        record,
        {
            "scenario_id",
            "language",
            "model",
            "rater_id",
            "scores",
            "critical_failures",
        },
        label,
    )
    for field in ("scenario_id", "language", "model", "rater_id"):
        _require_string(record, field, label)
    if record["language"] not in {"en", "vi"}:
        raise ValidationError(f"{label}: language must be 'en' or 'vi'")
    if not isinstance(record["scores"], dict) or not record["scores"]:
        raise ValidationError(f"{label}: scores must be a non-empty object")
    if any(not isinstance(dimension, str) for dimension in record["scores"]):
        raise ValidationError(f"{label}: score dimension names must be strings")
    unknown_dimensions = sorted(set(record["scores"]) - set(DIMENSION_WEIGHTS))
    if unknown_dimensions:
        raise ValidationError(f"{label}: unknown score dimensions: {', '.join(unknown_dimensions)}")
    for dimension, score in record["scores"].items():
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or not 1 <= score <= 5
        ):
            raise ValidationError(f"{label}: {dimension} score must be between 1 and 5")
    _validate_string_array(
        record["critical_failures"],
        "critical_failures",
        label,
        non_empty=False,
    )
    unknown_failures = sorted(set(record["critical_failures"]) - set(CRITICAL_FAILURE_PENALTIES))
    if unknown_failures:
        raise ValidationError(f"{label}: unknown critical failures: {', '.join(unknown_failures)}")


def load_scenarios(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate a scenario JSONL file."""
    records = _load_jsonl(path)
    seen: set[tuple[str, str]] = set()
    for record in records:
        validate_scenario(record)
        identity = (record["scenario_id"], record["language"])
        if identity in seen:
            raise ValidationError(
                f"duplicate scenario_id/language pair: {identity[0]}/{identity[1]}"
            )
        seen.add(identity)
        record.pop("_source_line", None)
    return records


def load_annotations(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate a human-annotation JSONL file."""
    records = _load_jsonl(path)
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        validate_annotation(record)
        identity = (
            record["scenario_id"],
            record["language"],
            record["model"],
            record["rater_id"],
        )
        if identity in seen:
            raise ValidationError(
                "duplicate scenario_id/language/model/rater_id tuple: "
                f"{identity[0]}/{identity[1]}/{identity[2]}/{identity[3]}"
            )
        seen.add(identity)
        record.pop("_source_line", None)
    return records
