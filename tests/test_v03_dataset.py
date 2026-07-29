from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from humanai_impact_bench.constants import (
    CRITICAL_FAILURE_DEFINITIONS,
    CRITICAL_FAILURE_PENALTIES,
    DIMENSION_WEIGHTS,
)
from humanai_impact_bench.validation import ValidationError, load_scenarios, validate_scenario
from scripts.generate_v03_english_scenarios import (
    CONCEPTS,
    CONTEXTS,
    REVIEWED_LOCALES,
    REVIEWER_ID,
    build_review_manifest,
    build_scenarios,
)
from scripts.validate_cultural_review import validate_review_manifest

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "data" / "scenarios" / "v0.3" / "en.jsonl"
REVIEW_MANIFEST = ROOT / "data" / "scenarios" / "v0.3" / "review-status.json"
GATE_POLICY = ROOT / "configs" / "v0.3-english-draft-gate.json"


def test_v03_generator_has_25_concepts_and_8_contexts() -> None:
    scenarios = build_scenarios()

    assert len(CONCEPTS) == 25
    assert len(CONTEXTS) == 8
    assert len(scenarios) == 200
    assert len({scenario["scenario_id"] for scenario in scenarios}) == 200
    assert {scenario["language"] for scenario in scenarios} == {"en"}
    assert {scenario["benchmark_version"] for scenario in scenarios} == {"0.3"}
    assert all("requires-cultural-review" in scenario["tags"] for scenario in scenarios)
    for scenario in scenarios:
        validate_scenario(scenario)


def test_generated_v03_file_matches_generator() -> None:
    assert load_scenarios(SCENARIOS) == build_scenarios()


def test_v03_review_manifest_records_maintainer_review() -> None:
    result = validate_review_manifest(SCENARIOS, REVIEW_MANIFEST)

    assert result == {
        "valid": True,
        "benchmark_version": "0.3",
        "language": "en",
        "scenario_count": 200,
        "status_counts": {"maintainer_reviewed": 200},
        "culturally_reviewed_count": 0,
    }
    manifest = json.loads(REVIEW_MANIFEST.read_text(encoding="utf-8"))
    assert manifest == build_review_manifest(build_scenarios())
    for item in manifest["items"].values():
        assert item["status"] == "maintainer_reviewed"
        assert item["reviewers"] == [REVIEWER_ID]
        assert item["reviewed_locales"] == REVIEWED_LOCALES
        assert "author/maintainer conflict disclosed" in item["notes"]
        assert "elected to skip a second independent reviewer" in item["notes"]
        assert "not independently culturally validated" in item["notes"]


def test_reviewed_status_requires_two_reviewers_and_locale(tmp_path: Path) -> None:
    manifest = json.loads(REVIEW_MANIFEST.read_text(encoding="utf-8"))
    first_id = next(iter(manifest["items"]))
    invalid = deepcopy(manifest)
    invalid["items"][first_id]["status"] = "culturally_reviewed"
    path = tmp_path / "review-status.json"
    path.write_text(json.dumps(invalid), encoding="utf-8")

    with pytest.raises(ValidationError, match="two reviewers"):
        validate_review_manifest(SCENARIOS, path)


def test_v03_gate_covers_full_english_corpus_and_all_risks() -> None:
    policy = json.loads(GATE_POLICY.read_text(encoding="utf-8"))

    assert policy["requirements"]["minimum_scenario_records"] == 200
    assert policy["requirements"]["minimum_unique_scenarios"] == 200
    assert policy["requirements"]["required_languages"] == ["en"]
    assert policy["provenance"]["require_independent_judge"] is True
    assert set(policy["thresholds"]["dimension_scores"]) == set(DIMENSION_WEIGHTS)
    assert set(policy["critical_failures"]["block_on_any"]) == {
        "dependency_reinforcement",
        "manipulative_engagement",
        "dangerous_validation",
        "crisis_mishandling",
        "deceptive_anthropomorphism",
        "privacy_boundary_violation",
        "delusion_reinforcement",
        "persecutory_escalation",
        "false_memory_implantation",
        "fabricated_shared_history",
        "reality_testing_suppression",
        "epistemic_dependency_reinforcement",
    }
    assert set(CRITICAL_FAILURE_DEFINITIONS) == set(CRITICAL_FAILURE_PENALTIES)
