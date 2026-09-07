"""Verify content-free commitments for access-controlled blind scenario sets."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from humanai_impact_bench.deployment import load_scenario_source
from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.validation import ValidationError

_MANIFEST_FIELDS = {
    "manifest_version",
    "commitment_algorithm",
    "scenario_count",
    "track_counts",
    "language_counts",
    "category_counts",
    "commitments",
}
_COMMITMENT_FIELDS = {
    "benchmark_track",
    "category",
    "language",
    "scenario_id",
    "scenario_sha256",
}
_ALGORITHM = "sha256-canonical-json-v1"


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {path}") from exc
    except OSError as exc:
        raise ValidationError(f"could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc.msg}") from exc
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_FIELDS:
        raise ValidationError("blind-set manifest has invalid fields")
    if manifest["manifest_version"] != "0.1":
        raise ValidationError("blind-set manifest_version must be '0.1'")
    if manifest["commitment_algorithm"] != _ALGORITHM:
        raise ValidationError(f"blind-set commitment_algorithm must be {_ALGORITHM!r}")
    if not isinstance(manifest["scenario_count"], int) or isinstance(
        manifest["scenario_count"], bool
    ):
        raise ValidationError("blind-set scenario_count must be an integer")
    if not isinstance(manifest["commitments"], list):
        raise ValidationError("blind-set commitments must be a list")
    for name in ("track_counts", "language_counts", "category_counts"):
        counts = manifest[name]
        if not isinstance(counts, dict) or any(
            not isinstance(key, str)
            or not isinstance(value, int)
            or isinstance(value, bool)
            or value < 1
            for key, value in counts.items()
        ):
            raise ValidationError(f"blind-set {name} must map names to positive integers")
    return manifest


def _identity(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        item["benchmark_track"],
        item["language"],
        item["category"],
        item["scenario_id"],
    )


def _validate_commitments(commitments: list[Any]) -> list[dict[str, str]]:
    if any(not isinstance(item, dict) or set(item) != _COMMITMENT_FIELDS for item in commitments):
        raise ValidationError("blind-set commitment has invalid fields")
    if any(
        any(not isinstance(item[field], str) or not item[field] for field in _COMMITMENT_FIELDS)
        for item in commitments
    ):
        raise ValidationError("blind-set commitment values must be non-empty strings")
    if any(
        len(item["scenario_sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in item["scenario_sha256"])
        for item in commitments
    ):
        raise ValidationError("blind-set commitment digest must be lowercase SHA-256")
    typed = commitments
    if typed != sorted(typed, key=_identity):
        raise ValidationError("blind-set commitments must be sorted")
    if len({_identity(item) for item in typed}) != len(typed):
        raise ValidationError("blind-set commitments contain duplicate identities")
    return typed


def verify_blind_set(manifest_path: Path, scenarios_path: Path) -> dict[str, Any]:
    """Verify a supplied scenario source against a content-free manifest."""
    manifest = _load_manifest(Path(manifest_path))
    commitments = _validate_commitments(manifest["commitments"])
    scenarios, _dataset_digest = load_scenario_source(scenarios_path)
    if any(scenario.get("benchmark_version") != "0.7" for scenario in scenarios):
        raise ValidationError("blind-set scenarios must use benchmark_version '0.7'")
    if len(scenarios) != manifest["scenario_count"] or len(commitments) != len(scenarios):
        raise ValidationError("blind-set scenario count does not match commitments")

    track_counts = dict(
        sorted(Counter(scenario["benchmark_track"] for scenario in scenarios).items())
    )
    language_counts = dict(sorted(Counter(scenario["language"] for scenario in scenarios).items()))
    category_counts = dict(sorted(Counter(scenario["category"] for scenario in scenarios).items()))
    if (
        manifest["track_counts"] != track_counts
        or manifest["language_counts"] != language_counts
        or manifest["category_counts"] != category_counts
    ):
        raise ValidationError("blind-set declared counts do not match scenarios")

    actual = sorted(
        [
            {
                "benchmark_track": scenario["benchmark_track"],
                "category": scenario["category"],
                "language": scenario["language"],
                "scenario_id": scenario["scenario_id"],
                "scenario_sha256": record_digest(scenario),
            }
            for scenario in scenarios
        ],
        key=_identity,
    )
    if commitments != actual:
        raise ValidationError("blind-set commitment mismatch")
    return {
        "valid": True,
        "scenario_count": len(scenarios),
        "commitment_algorithm": _ALGORITHM,
    }
