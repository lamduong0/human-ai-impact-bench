from __future__ import annotations

import json
from pathlib import Path

import pytest

from humanai_impact_bench.constants import CATEGORIES, DIMENSION_WEIGHTS, RISK_LEVELS
from humanai_impact_bench.validation import ValidationError, load_scenarios, validate_scenario
from scripts import generate_v04_review_manifest
from scripts.validate_cultural_review import validate_review_manifest

ROOT = Path(__file__).resolve().parents[1]
V04_DIR = ROOT / "data" / "scenarios" / "v0.4"
REVIEW_MANIFEST = V04_DIR / "review-status.json"
NEW_CATEGORIES = {
    "engagement_manipulation",
    "ideological_steering",
    "romantic_sexual_boundaries",
    "moral_outsourcing_and_deskilling",
    "abuse_and_harassment_dynamics",
    "identity_and_dignity_harm",
    "compulsive_use_and_displacement",
}


def _all_v04_scenarios() -> list[dict]:
    scenarios: list[dict] = []
    for path in sorted(V04_DIR.glob("*.jsonl")):
        scenarios.extend(load_scenarios(path))
    return scenarios


def test_v04_categories_are_registered() -> None:
    assert NEW_CATEGORIES <= CATEGORIES


def test_v04_scenarios_validate_and_are_well_formed() -> None:
    scenarios = _all_v04_scenarios()

    assert len(scenarios) == 56
    assert len({scenario["scenario_id"] for scenario in scenarios}) == 56
    assert {scenario["benchmark_version"] for scenario in scenarios} == {"0.4"}
    assert {scenario["language"] for scenario in scenarios} == {"en"}

    per_category: dict[str, int] = {}
    for scenario in scenarios:
        validate_scenario(scenario)
        assert "requires-cultural-review" in scenario["tags"]
        assert set(scenario["dimensions"]) <= set(DIMENSION_WEIGHTS)
        assert scenario["risk_level"] in RISK_LEVELS
        per_category[scenario["category"]] = per_category.get(scenario["category"], 0) + 1

    assert set(per_category) == NEW_CATEGORIES
    assert all(count == 8 for count in per_category.values())


def test_v04_review_manifest_covers_all_scenarios_as_unreviewed() -> None:
    result = validate_review_manifest(V04_DIR, REVIEW_MANIFEST)

    assert result == {
        "valid": True,
        "benchmark_version": "0.4",
        "language": "en",
        "scenario_count": 56,
        "status_counts": {"draft_unreviewed": 56},
        "culturally_reviewed_count": 0,
    }


def test_v04_review_manifest_matches_generator() -> None:
    assert (
        json.loads(REVIEW_MANIFEST.read_text(encoding="utf-8"))
        == generate_v04_review_manifest.build_manifest()
    )


def test_v04_review_manifest_rejects_duplicate_scenario_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario_line = next(V04_DIR.glob("*.jsonl")).read_text(encoding="utf-8").splitlines()[0]
    (tmp_path / "first.jsonl").write_text(scenario_line + "\n", encoding="utf-8")
    (tmp_path / "second.jsonl").write_text(scenario_line + "\n", encoding="utf-8")
    monkeypatch.setattr(generate_v04_review_manifest, "SCENARIOS_DIR", tmp_path)

    with pytest.raises(ValidationError, match="duplicate scenario_id"):
        generate_v04_review_manifest.build_manifest()
