from __future__ import annotations

from pathlib import Path

from humanai_impact_bench.constants import CATEGORIES, DIMENSION_WEIGHTS, RISK_LEVELS
from humanai_impact_bench.validation import load_scenarios, validate_scenario

ROOT = Path(__file__).resolve().parents[1]
V04_DIR = ROOT / "data" / "scenarios" / "v0.4"
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
        assert set(scenario["dimensions"]) <= set(DIMENSION_WEIGHTS)
        assert scenario["risk_level"] in RISK_LEVELS
        per_category[scenario["category"]] = per_category.get(scenario["category"], 0) + 1

    assert set(per_category) == NEW_CATEGORIES
    assert all(count == 8 for count in per_category.values())
