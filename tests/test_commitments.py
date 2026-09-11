from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from humanai_impact_bench.commitments import verify_blind_set
from humanai_impact_bench.validation import ValidationError


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return path


def _manifest(scenarios: list[dict]) -> dict:
    import hashlib

    def digest(record: dict) -> str:
        payload = json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    commitments = sorted(
        [
            {
                "benchmark_track": scenario["benchmark_track"],
                "category": scenario["category"],
                "language": scenario["language"],
                "scenario_id": scenario["scenario_id"],
                "scenario_sha256": digest(scenario),
            }
            for scenario in scenarios
        ],
        key=lambda item: (
            item["benchmark_track"],
            item["language"],
            item["category"],
            item["scenario_id"],
        ),
    )
    return {
        "manifest_version": "0.1",
        "commitment_algorithm": "sha256-canonical-json-v1",
        "scenario_count": len(scenarios),
        "track_counts": {"core": len(scenarios)},
        "language_counts": {"en": len(scenarios)},
        "category_counts": {"dependency_boundaries": len(scenarios)},
        "commitments": commitments,
    }


def _scenarios(scenario_factory: Callable[..., dict]) -> list[dict]:
    return [
        scenario_factory(
            benchmark_version="0.7",
            benchmark_track="core",
            scenario_id="blind-001",
        ),
        scenario_factory(
            benchmark_version="0.7",
            benchmark_track="core",
            scenario_id="blind-002",
        ),
    ]


def test_verify_blind_set_accepts_exact_commitments(
    tmp_path: Path, scenario_factory: Callable[..., dict]
) -> None:
    scenarios = _scenarios(scenario_factory)
    scenarios_path = _write_jsonl(tmp_path / "blind.jsonl", scenarios)
    manifest_path = tmp_path / "blind-manifest.json"
    manifest_path.write_text(json.dumps(_manifest(scenarios)), encoding="utf-8")

    assert verify_blind_set(manifest_path, scenarios_path) == {
        "valid": True,
        "scenario_count": 2,
        "commitment_algorithm": "sha256-canonical-json-v1",
    }


def test_verify_blind_set_rejects_changed_prompt(
    tmp_path: Path, scenario_factory: Callable[..., dict]
) -> None:
    scenarios = _scenarios(scenario_factory)
    scenarios_path = _write_jsonl(tmp_path / "blind.jsonl", scenarios)
    manifest_path = tmp_path / "blind-manifest.json"
    manifest_path.write_text(json.dumps(_manifest(scenarios)), encoding="utf-8")
    scenarios[0]["initial_prompt"] = "changed but never exposed"
    _write_jsonl(scenarios_path, scenarios)

    with pytest.raises(ValidationError, match="commitment mismatch"):
        verify_blind_set(manifest_path, scenarios_path)
