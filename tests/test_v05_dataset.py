from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from humanai_impact_bench.constants import CATEGORIES, DIMENSION_WEIGHTS, RISK_LEVELS
from humanai_impact_bench.validation import (
    ValidationError,
    load_scenarios,
    validate_scenario,
)
from scripts import audit_scenario_coverage, generate_v05_review_manifest
from scripts.validate_cultural_review import validate_review_manifest

ROOT = Path(__file__).resolve().parents[1]
V05_DIR = ROOT / "data" / "scenarios" / "v0.5"
REVIEW_MANIFEST = V05_DIR / "review-status.json"
COVERAGE_STANDARD = json.loads(
    (ROOT / "configs" / "scenario-coverage-standard.json").read_text(encoding="utf-8")
)
V05_CATEGORIES = {
    "personalized_vulnerability_exploitation",
    "memory_consent_and_personalization",
    "cross_session_dependency_and_recovery",
    "relationship_guidance_and_triangulation",
    "cognitive_scaffolding_and_metacognition",
    "institutional_authority_and_workplace_coercion",
    "emotion_inference_and_surveillance",
    "grief_identity_and_memorial_simulation",
}
RECORDS_PER_CATEGORY = COVERAGE_STANDARD["v0.5"]["active_checkpoint_records_per_category"]
TOTAL_RECORDS = len(V05_CATEGORIES) * RECORDS_PER_CATEGORY
TOTAL_PAIRS = TOTAL_RECORDS // COVERAGE_STANDARD["v0.5"]["matched_records_per_construct"]


def _all_v05_scenarios() -> list[dict]:
    return [
        scenario for path in sorted(V05_DIR.glob("*.jsonl")) for scenario in load_scenarios(path)
    ]


def test_v05_categories_are_registered() -> None:
    assert V05_CATEGORIES <= CATEGORIES


def test_v05_coverage_standard_is_coherent() -> None:
    assert COVERAGE_STANDARD["mature_records_per_category"] == 100
    assert COVERAGE_STANDARD["development_checkpoints"] == [30, 50, 80, 100]
    assert COVERAGE_STANDARD["v0.5"] == {
        "category_count": 8,
        "categories": [
            "personalized_vulnerability_exploitation",
            "memory_consent_and_personalization",
            "cross_session_dependency_and_recovery",
            "relationship_guidance_and_triangulation",
            "cognitive_scaffolding_and_metacognition",
            "institutional_authority_and_workplace_coercion",
            "emotion_inference_and_surveillance",
            "grief_identity_and_memorial_simulation",
        ],
        "active_checkpoint_records_per_category": 50,
        "matched_records_per_construct": 2,
        "mature_constructs_per_category": 50,
    }
    assert set(COVERAGE_STANDARD["v0.5"]["categories"]) == V05_CATEGORIES
    assert RECORDS_PER_CATEGORY <= COVERAGE_STANDARD["mature_records_per_category"]
    v06 = COVERAGE_STANDARD["v0.6"]
    assert v06["planned_total_records"] == (
        v06["planned_category_count"] * v06["mature_records_per_category"]
    )
    assert (
        v06["bilingual_category_count"] * v06["records_per_language_in_bilingual_category"] * 2
        == 1600
    )


def test_v05_pilot_is_complete_and_structurally_valid() -> None:
    scenarios = _all_v05_scenarios()

    assert len(scenarios) == TOTAL_RECORDS
    assert len({scenario["scenario_id"] for scenario in scenarios}) == TOTAL_RECORDS
    assert {scenario["benchmark_version"] for scenario in scenarios} == {"0.5"}
    assert {scenario["language"] for scenario in scenarios} == {"en"}
    assert {scenario["locale"] for scenario in scenarios} == {"en-US", "en-VN"}

    category_counts = Counter(scenario["category"] for scenario in scenarios)
    assert set(category_counts) == V05_CATEGORIES
    assert set(category_counts.values()) == {RECORDS_PER_CATEGORY}
    assert Counter(scenario["locale"] for scenario in scenarios) == {
        "en-US": TOTAL_RECORDS // 2,
        "en-VN": TOTAL_RECORDS // 2,
    }
    half_category = RECORDS_PER_CATEGORY // 2
    expected_category_locale_counts = (
        {half_category} if half_category % 2 == 0 else {half_category - 1, half_category + 1}
    )
    for category in V05_CATEGORIES:
        locale_counts = Counter(
            scenario["locale"] for scenario in scenarios if scenario["category"] == category
        )
        assert set(locale_counts.values()) == expected_category_locale_counts

    for scenario in scenarios:
        validate_scenario(scenario)
        assert scenario["risk_level"] in RISK_LEVELS
        assert set(scenario["dimensions"]) <= set(DIMENSION_WEIGHTS)
        assert "requires-cultural-review" in scenario["tags"]
        assert f"protocol-{scenario['protocol_mode']}" in scenario["tags"]
        assert f"locale-{scenario['locale']}" in scenario["tags"]
        assert sum(tag.startswith("concept-") for tag in scenario["tags"]) == 1
        assert sum(tag.startswith("context-") for tag in scenario["tags"]) == 1


def test_v05_matched_pairs_are_balanced_and_comparable() -> None:
    scenarios = _all_v05_scenarios()
    by_pair: dict[str, list[dict]] = defaultdict(list)
    for scenario in scenarios:
        by_pair[scenario["matched_pair_id"]].append(scenario)

    assert len(by_pair) == TOTAL_PAIRS
    for members in by_pair.values():
        assert len(members) == 2
        assert {member["protocol_mode"] for member in members} == {
            "continuous",
            "prefill_recovery",
        }
        for field in (
            "category",
            "language",
            "locale",
            "risk_level",
            "dimensions",
            "initial_prompt",
            "follow_up_prompts",
        ):
            values = {
                json.dumps(member[field], ensure_ascii=False, sort_keys=True) for member in members
            }
            assert len(values) == 1
        concept_tags = {
            next(tag for tag in member["tags"] if tag.startswith("concept-")) for member in members
        }
        assert len(concept_tags) == 1

        continuous = next(member for member in members if member["protocol_mode"] == "continuous")
        recovery = next(
            member for member in members if member["protocol_mode"] == "prefill_recovery"
        )
        assert "prefill_messages" not in continuous
        assert len(recovery["prefill_messages"]) in {2, 4}

    concept_counts = Counter(
        tag for scenario in scenarios for tag in scenario["tags"] if tag.startswith("concept-")
    )
    assert set(concept_counts.values()) == {2}
    context_tags = [
        tag for scenario in scenarios for tag in scenario["tags"] if tag.startswith("context-")
    ]
    assert len(context_tags) == TOTAL_RECORDS
    assert len(set(context_tags)) == TOTAL_RECORDS


def test_v05_review_manifest_is_valid_and_digest_bound() -> None:
    result = validate_review_manifest(V05_DIR, REVIEW_MANIFEST)

    assert result["valid"] is True
    assert result["benchmark_version"] == "0.5"
    assert result["language"] == "en"
    assert result["scenario_count"] == TOTAL_RECORDS
    assert sum(result["status_counts"].values()) == TOTAL_RECORDS
    manifest = json.loads(REVIEW_MANIFEST.read_text(encoding="utf-8"))
    assert len(manifest["items"]) == TOTAL_RECORDS
    for item in manifest["items"].values():
        assert item["status"] in manifest["allowed_statuses"]
        if item["status"] == "draft_unreviewed":
            assert item["reviewers"] == []
            assert item["reviewed_locales"] == []
        assert len(item["scenario_digest"]) == 64


def test_v05_review_manifest_matches_generator() -> None:
    current_manifest = json.loads(REVIEW_MANIFEST.read_text(encoding="utf-8"))
    assert current_manifest == generate_v05_review_manifest.build_manifest(
        existing_manifest=current_manifest
    )


def test_v05_review_manifest_records_disclosed_maintainer_review() -> None:
    manifest = json.loads(REVIEW_MANIFEST.read_text(encoding="utf-8"))

    for item in manifest["items"].values():
        assert item["status"] == "maintainer_reviewed"
        assert item["reviewers"] == ["lamduong0"]
        assert item["reviewed_locales"] == ["en-US", "en-VN"]
        assert "author/maintainer conflict disclosed" in item["notes"]
        assert "elected to skip a second independent reviewer" in item["notes"]
        assert "not independently culturally validated" in item["notes"]


def test_v05_manifest_generator_preserves_only_unchanged_review_items() -> None:
    existing = generate_v05_review_manifest.build_manifest()
    scenario_id = next(iter(existing["items"]))
    existing_item = existing["items"][scenario_id]
    existing_item.update(
        {
            "status": "maintainer_reviewed",
            "reviewers": ["reviewer"],
            "reviewed_locales": ["en-US"],
            "notes": "Reviewed test fixture.",
        }
    )

    preserved = generate_v05_review_manifest.build_manifest(existing_manifest=existing)
    assert preserved["items"][scenario_id]["status"] == "maintainer_reviewed"

    existing_item["scenario_digest"] = "0" * 64
    reset = generate_v05_review_manifest.build_manifest(existing_manifest=existing)
    assert reset["items"][scenario_id]["status"] == "draft_unreviewed"
    assert reset["items"][scenario_id]["reviewers"] == []


def test_v05_review_manifest_requires_scenario_digest(tmp_path: Path) -> None:
    manifest = generate_v05_review_manifest.build_manifest()
    scenario_id = next(iter(manifest["items"]))
    del manifest["items"][scenario_id]["scenario_digest"]
    manifest_path = tmp_path / "review-status.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValidationError, match="invalid fields"):
        validate_review_manifest(V05_DIR, manifest_path)


def test_v05_passes_coverage_audit() -> None:
    report = audit_scenario_coverage.build_report(
        V05_DIR,
        expected_per_category=RECORDS_PER_CATEGORY,
        expected_categories=V05_CATEGORIES,
        matched=True,
    )

    assert report["valid"], report
    assert report["scenario_count"] == TOTAL_RECORDS
    assert report["duplicate_prompt_groups"] == []
    for component in (
        "context",
        "follow_up_prompts",
        "expected_behaviors",
        "failure_modes",
    ):
        assert report["repeated_component_groups"][component] == []
    assert report["pair_violations"] == []


def test_coverage_audit_rejects_a_partial_checkpoint() -> None:
    partial_source = V05_DIR / "cross_session_dependency_and_recovery.jsonl"
    report = audit_scenario_coverage.build_report(
        partial_source,
        expected_per_category=RECORDS_PER_CATEGORY,
        expected_categories=V05_CATEGORIES,
        matched=True,
    )

    assert not report["valid"]
    assert any(issue.startswith("missing categories:") for issue in report["issues"])
