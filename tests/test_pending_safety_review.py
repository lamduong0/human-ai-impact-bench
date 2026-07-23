from __future__ import annotations

from pathlib import Path

from humanai_impact_bench.constants import CATEGORIES, DIMENSION_WEIGHTS, RISK_LEVELS
from humanai_impact_bench.validation import load_scenarios, validate_scenario

ROOT = Path(__file__).resolve().parents[1]
PENDING_DIR = ROOT / "data" / "scenarios" / "pending-safety-review"
V04_DIR = ROOT / "data" / "scenarios" / "v0.4"
SENSITIVE_CATEGORIES = {"self_harm_and_suicide", "minor_safety"}


def _pending_scenarios() -> list[dict]:
    scenarios: list[dict] = []
    for path in sorted(PENDING_DIR.glob("*.jsonl")):
        scenarios.extend(load_scenarios(path))
    return scenarios


def test_sensitive_categories_are_registered() -> None:
    assert SENSITIVE_CATEGORIES <= CATEGORIES


def test_pending_scenarios_valid_tagged_and_well_formed() -> None:
    scenarios = _pending_scenarios()

    assert len(scenarios) == 16
    assert len({scenario["scenario_id"] for scenario in scenarios}) == 16

    per_category: dict[str, int] = {}
    for scenario in scenarios:
        validate_scenario(scenario)
        # Every quarantined draft must carry the review gate marker.
        assert "requires-safety-review" in scenario["tags"]
        assert set(scenario["dimensions"]) <= set(DIMENSION_WEIGHTS)
        assert scenario["risk_level"] in RISK_LEVELS
        per_category[scenario["category"]] = per_category.get(scenario["category"], 0) + 1

    assert set(per_category) == SENSITIVE_CATEGORIES
    assert all(count == 8 for count in per_category.values())


def test_sensitive_drafts_are_quarantined_from_released_corpus() -> None:
    # Invariant: sensitive categories must not leak into the released v0.4 corpus
    # until they pass clinical/safety review.
    for path in V04_DIR.glob("*.jsonl"):
        for scenario in load_scenarios(path):
            assert scenario["category"] not in SENSITIVE_CATEGORIES
