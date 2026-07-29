from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from humanai_impact_bench.validation import (
    ValidationError,
    load_scenarios,
    validate_scenario,
)
from scripts import (
    audit_scenario_coverage,
    audit_scenario_similarity,
    generate_v06_lineage_index,
    generate_v06_review_manifest,
    generate_v06_stage1_selection,
)
from scripts.validate_cultural_review import validate_review_manifest

ROOT = Path(__file__).resolve().parents[1]
V06_DIR = ROOT / "data" / "scenarios" / "v0.6"
EN_DIR = V06_DIR / "en"
EN_REVIEW_MANIFEST = EN_DIR / "review-status.json"
LINEAGE_INDEX = V06_DIR / "lineage-index.json"
SIMILARITY_AUDIT = V06_DIR / "stage1-lexical-similarity-audit.json"
STAGE1_SELECTION = V06_DIR / "stage1-selection.json"
STAGE1_CATEGORIES = {
    "abuse_and_harassment_dynamics",
    "compulsive_use_and_displacement",
    "engagement_manipulation",
    "identity_and_dignity_harm",
    "ideological_steering",
    "moral_outsourcing_and_deskilling",
    "romantic_sexual_boundaries",
}
RECORDS_PER_CATEGORY = 30
TOTAL_RECORDS = len(STAGE1_CATEGORIES) * RECORDS_PER_CATEGORY


def _scenarios() -> list[dict]:
    selection = json.loads(STAGE1_SELECTION.read_text(encoding="utf-8"))
    selected_ids = {item["scenario_id"] for item in selection["items"]}
    return [
        scenario
        for path in sorted(EN_DIR.glob("*.jsonl"))
        for scenario in load_scenarios(path)
        if scenario["scenario_id"] in selected_ids
    ]


def _single_tag(scenario: dict, prefix: str) -> str:
    values = [tag for tag in scenario["tags"] if tag.startswith(prefix)]
    assert len(values) == 1, scenario["scenario_id"]
    return values[0]


def test_v06_stage1_foundation_is_complete_and_valid() -> None:
    scenarios = _scenarios()

    assert len(scenarios) == TOTAL_RECORDS
    assert len({scenario["scenario_id"] for scenario in scenarios}) == TOTAL_RECORDS
    assert {scenario["benchmark_version"] for scenario in scenarios} == {"0.6"}
    assert {scenario["language"] for scenario in scenarios} == {"en"}
    assert Counter(scenario["category"] for scenario in scenarios) == {
        category: RECORDS_PER_CATEGORY for category in STAGE1_CATEGORIES
    }

    concept_tags: list[str] = []
    context_tags: list[str] = []
    for scenario in scenarios:
        validate_scenario(scenario)
        assert len(scenario) == 14
        assert "requires-cultural-review" in scenario["tags"]
        concept_tags.append(_single_tag(scenario, "concept-"))
        context_tags.append(_single_tag(scenario, "context-"))
        derivation = _single_tag(scenario, "derivation-")
        if derivation == "derivation-adapted":
            _single_tag(scenario, "source-version-")
            _single_tag(scenario, "source-scenario-")
        else:
            assert derivation == "derivation-authored-new"
            assert not any(
                tag.startswith(("source-version-", "source-scenario-")) for tag in scenario["tags"]
            )

    assert len(concept_tags) == len(set(concept_tags)) == TOTAL_RECORDS
    assert len(context_tags) == len(set(context_tags)) == TOTAL_RECORDS


def test_v06_stage1_passes_deterministic_exact_audit() -> None:
    selection = json.loads(STAGE1_SELECTION.read_text(encoding="utf-8"))
    selection_identities = {(item["language"], item["scenario_id"]) for item in selection["items"]}
    report = audit_scenario_coverage.build_report(
        EN_DIR,
        expected_per_category=RECORDS_PER_CATEGORY,
        expected_categories=STAGE1_CATEGORIES,
        selection_identities=selection_identities,
        strict_list_items=True,
    )

    assert report["valid"], report
    assert report["duplicate_prompt_groups"] == []
    assert all(not groups for groups in report["repeated_component_groups"].values())


def test_v06_stage1_lineage_index_matches_scenarios() -> None:
    index = json.loads(LINEAGE_INDEX.read_text(encoding="utf-8"))
    selection = json.loads(STAGE1_SELECTION.read_text(encoding="utf-8"))
    selection_identities = {(item["language"], item["scenario_id"]) for item in selection["items"]}
    selected_items = [
        item
        for item in index["items"]
        if (item["target_language"], item["target_scenario_id"]) in selection_identities
    ]

    assert len(selected_items) == TOTAL_RECORDS
    assert Counter(item["derivation"] for item in selected_items) == {
        "adapted": 56,
        "authored_new": 154,
    }


def test_v06_stage1_review_manifest_records_maintainer_approval() -> None:
    result = validate_review_manifest(EN_DIR, EN_REVIEW_MANIFEST)

    assert result["valid"] is True
    assert result["benchmark_version"] == "0.6"
    assert result["language"] == "en"
    assert result["scenario_count"] >= TOTAL_RECORDS
    assert result["status_counts"]["maintainer_reviewed"] >= TOTAL_RECORDS
    assert result["culturally_reviewed_count"] == 0
    manifest = json.loads(EN_REVIEW_MANIFEST.read_text(encoding="utf-8"))
    assert manifest == generate_v06_review_manifest.build_manifest(
        "en",
        existing_manifest=manifest,
    )
    selection = json.loads(STAGE1_SELECTION.read_text(encoding="utf-8"))
    reviewed_items = [manifest["items"][item["scenario_id"]] for item in selection["items"]]
    assert all(len(item["scenario_digest"]) == 64 for item in reviewed_items)
    assert all(item["status"] == "maintainer_reviewed" for item in reviewed_items)
    assert all(item["reviewers"] == ["lamduong0"] for item in reviewed_items)
    assert all(item["reviewed_locales"] == ["en-US", "en-VN"] for item in reviewed_items)
    assert all(
        "author/maintainer conflict disclosed" in item["notes"]
        and "skip a second independent reviewer" in item["notes"]
        and "not independently culturally validated" in item["notes"]
        for item in reviewed_items
    )
    regenerated = generate_v06_review_manifest.build_manifest(
        "en",
        maintainer_review_stage1=True,
    )
    selected_ids = {item["scenario_id"] for item in selection["items"]}
    assert {
        scenario_id
        for scenario_id, item in regenerated["items"].items()
        if item["status"] == "maintainer_reviewed"
    } == selected_ids


def test_v06_stage1_similarity_audit_is_reproducible() -> None:
    report = json.loads(SIMILARITY_AUDIT.read_text(encoding="utf-8"))
    selection = json.loads(STAGE1_SELECTION.read_text(encoding="utf-8"))
    selection_identities = {(item["language"], item["scenario_id"]) for item in selection["items"]}
    compare_sources = [
        ROOT / "data" / "scenarios" / version
        for version in ("v0.1", "v0.2", "v0.3", "v0.4", "v0.5")
    ]

    assert report == audit_scenario_similarity.build_report(
        EN_DIR,
        compare_sources=compare_sources,
        selection_identities=selection_identities,
    )
    assert report["audit_scope"] == "lexical_candidate_generation"
    assert report["scenario_count"] == TOTAL_RECORDS
    assert report["authored_new_count"] == 154
    assert report["historical_scenario_count"] == 688
    assert report["selection_identity_count"] == TOTAL_RECORDS
    assert report["candidate_count"] == 0
    assert report["limitations"]


def test_v06_stage1_selection_is_digest_bound_and_reproducible() -> None:
    selection = json.loads(STAGE1_SELECTION.read_text(encoding="utf-8"))

    assert selection == generate_v06_stage1_selection.build_selection()
    assert selection["scenario_count"] == TOTAL_RECORDS
    assert all(len(item["scenario_sha256"]) == 64 for item in selection["items"])


def test_v06_manifest_preserves_only_unchanged_review_items() -> None:
    existing = generate_v06_review_manifest.build_manifest("en")
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

    preserved = generate_v06_review_manifest.build_manifest(
        "en",
        existing_manifest=existing,
    )
    assert preserved["items"][scenario_id]["status"] == "maintainer_reviewed"

    existing_item["scenario_digest"] = "0" * 64
    reset = generate_v06_review_manifest.build_manifest(
        "en",
        existing_manifest=existing,
    )
    assert reset["items"][scenario_id]["status"] == "draft_unreviewed"
    assert reset["items"][scenario_id]["reviewers"] == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("benchmark_version", "0.5"),
        ("language", "vi"),
    ],
)
def test_v06_generators_reject_misfiled_scenarios(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    scenario = dict(_scenarios()[0])
    scenario[field] = value
    v06_dir = tmp_path / "v0.6"
    language_dir = v06_dir / "en"
    language_dir.mkdir(parents=True)
    (language_dir / "invalid.jsonl").write_text(
        json.dumps(scenario, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(generate_v06_lineage_index, "V06_DIR", v06_dir)
    monkeypatch.setattr(generate_v06_review_manifest, "V06_DIR", v06_dir)

    with pytest.raises(ValidationError):
        generate_v06_lineage_index.build_index()
    with pytest.raises(ValidationError):
        generate_v06_review_manifest.build_manifest("en")


def test_v06_manifest_requires_cultural_review_tag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = dict(_scenarios()[0])
    scenario["tags"] = [tag for tag in scenario["tags"] if tag != "requires-cultural-review"]
    v06_dir = tmp_path / "v0.6"
    language_dir = v06_dir / "en"
    language_dir.mkdir(parents=True)
    (language_dir / "invalid.jsonl").write_text(
        json.dumps(scenario, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(generate_v06_review_manifest, "V06_DIR", v06_dir)

    with pytest.raises(ValidationError, match="missing requires-cultural-review"):
        generate_v06_review_manifest.build_manifest("en")


def test_v06_lineage_rejects_source_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory = json.loads(generate_v06_lineage_index.INVENTORY_PATH.read_text(encoding="utf-8"))
    inventory["items"][0]["content_sha256"] = "0" * 64
    inventory_path = tmp_path / "source-inventory.json"
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        generate_v06_lineage_index,
        "INVENTORY_PATH",
        inventory_path,
    )

    with pytest.raises(ValidationError, match="no longer matches the source inventory"):
        generate_v06_lineage_index.build_index()
