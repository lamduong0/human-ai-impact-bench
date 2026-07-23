from __future__ import annotations

from pathlib import Path

from humanai_impact_bench.constants import CATEGORIES, DIMENSION_WEIGHTS, RISK_LEVELS
from humanai_impact_bench.validation import load_scenarios, validate_scenario
from scripts.validate_cultural_review import validate_review_manifest

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIR = ROOT / "data" / "scenarios"
PENDING_DIR = SCENARIOS_DIR / "pending-safety-review"
PENDING_MANIFEST = PENDING_DIR / "review-status.json"
SENSITIVE_CATEGORIES = {"self_harm_and_suicide", "minor_safety"}
COUNTER_PROBE_IDS = {"self-harm-09", "minor-safety-10"}


def _pending_scenarios() -> list[dict]:
    assert PENDING_DIR.is_dir(), f"Missing pending-review directory: {PENDING_DIR}"
    scenarios: list[dict] = []
    for path in sorted(PENDING_DIR.glob("*.jsonl")):
        scenarios.extend(load_scenarios(path))
    return scenarios


def test_sensitive_categories_are_registered() -> None:
    assert SENSITIVE_CATEGORIES <= CATEGORIES


def test_pending_scenarios_valid_tagged_and_well_formed() -> None:
    scenarios = _pending_scenarios()

    assert len(scenarios) == 22
    assert len({scenario["scenario_id"] for scenario in scenarios}) == 22

    per_category: dict[str, int] = {}
    for scenario in scenarios:
        validate_scenario(scenario)
        # Every quarantined draft must carry the review gate marker.
        assert "requires-safety-review" in scenario["tags"]
        assert set(scenario["dimensions"]) <= set(DIMENSION_WEIGHTS)
        assert scenario["risk_level"] in RISK_LEVELS
        if scenario["scenario_id"] in COUNTER_PROBE_IDS:
            assert scenario["risk_level"] == "low"
        else:
            assert scenario["risk_level"] in {"high", "critical"}
        per_category[scenario["category"]] = per_category.get(scenario["category"], 0) + 1

    assert per_category == {"self_harm_and_suicide": 12, "minor_safety": 10}


def test_pending_review_manifest_covers_every_draft() -> None:
    result = validate_review_manifest(PENDING_DIR, PENDING_MANIFEST)

    assert result == {
        "valid": True,
        "benchmark_version": "0.4",
        "language": "en",
        "scenario_count": 22,
        "status_counts": {"draft_unreviewed": 22},
        "culturally_reviewed_count": 0,
    }


def test_sensitive_drafts_are_quarantined_from_released_corpus() -> None:
    # Invariant: sensitive categories must not leak into any released corpus
    # until they pass clinical/safety review.
    released_dirs = sorted(path for path in SCENARIOS_DIR.glob("v*") if path.is_dir())
    assert released_dirs, f"No released corpus directories found under {SCENARIOS_DIR}"
    assert SCENARIOS_DIR / "v0.4" in released_dirs
    for released_dir in released_dirs:
        for path in released_dir.glob("*.jsonl"):
            for scenario in load_scenarios(path):
                assert scenario["category"] not in SENSITIVE_CATEGORIES
