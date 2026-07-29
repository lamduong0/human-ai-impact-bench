from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from humanai_impact_bench.validation import load_scenarios, validate_scenario
from scripts import (
    audit_bilingual_pairs,
    audit_scenario_coverage,
    audit_scenario_similarity,
    audit_template_phrases,
    generate_v06_checkpoint_index,
    generate_v06_lineage_index,
    generate_v06_review_manifest,
)
from scripts.validate_cultural_review import validate_review_manifest

ROOT = Path(__file__).resolve().parents[1]
V06_DIR = ROOT / "data" / "scenarios" / "v0.6"
EN_DIR = V06_DIR / "en"
VI_DIR = V06_DIR / "vi"
COVERAGE = json.loads(
    (ROOT / "configs" / "scenario-coverage-standard.json").read_text(encoding="utf-8")
)["v0.6"]
BILINGUAL_CATEGORIES = set(COVERAGE["bilingual_categories"])
ENGLISH_FIRST_CATEGORIES = set(COVERAGE["english_first_categories"])
ALL_CATEGORIES = BILINGUAL_CATEGORIES | ENGLISH_FIRST_CATEGORIES
CHECKPOINT_COUNT = COVERAGE["first_complete_checkpoint_total_records"]
PHYSICAL_RECORDS_PER_CATEGORY = COVERAGE["first_complete_checkpoint_records_per_category"]
BILINGUAL_RECORDS_PER_LANGUAGE = COVERAGE[
    "first_complete_checkpoint_records_per_language_in_bilingual_category"
]


def _load_language(language: str) -> list[dict]:
    return [
        scenario
        for path in sorted((V06_DIR / language).glob("*.jsonl"))
        for scenario in load_scenarios(path)
    ]


def _single_tag(scenario: dict, prefix: str) -> str:
    values = [tag for tag in scenario["tags"] if tag.startswith(prefix)]
    assert len(values) == 1, scenario["scenario_id"]
    return values[0]


def test_v06_first_complete_checkpoint_is_balanced_and_valid() -> None:
    en_scenarios = _load_language("en")
    vi_scenarios = _load_language("vi")
    scenarios = en_scenarios + vi_scenarios

    assert len(scenarios) == CHECKPOINT_COUNT == 1200
    assert len({(scenario["language"], scenario["scenario_id"]) for scenario in scenarios}) == 1200
    assert Counter(scenario["category"] for scenario in scenarios) == {
        category: PHYSICAL_RECORDS_PER_CATEGORY for category in ALL_CATEGORIES
    }
    assert Counter(scenario["language"] for scenario in scenarios) == {"en": 800, "vi": 400}
    assert Counter(scenario["category"] for scenario in en_scenarios) == {
        **{category: BILINGUAL_RECORDS_PER_LANGUAGE for category in BILINGUAL_CATEGORIES},
        **{category: PHYSICAL_RECORDS_PER_CATEGORY for category in ENGLISH_FIRST_CATEGORIES},
    }
    assert Counter(scenario["category"] for scenario in vi_scenarios) == {
        category: BILINGUAL_RECORDS_PER_LANGUAGE for category in BILINGUAL_CATEGORIES
    }

    context_tags: list[str] = []
    for scenario in scenarios:
        validate_scenario(scenario)
        assert len(scenario) == 14
        assert scenario["benchmark_version"] == "0.6"
        assert "requires-cultural-review" in scenario["tags"]
        _single_tag(scenario, "concept-")
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
    assert len(context_tags) == len(set(context_tags)) == CHECKPOINT_COUNT


def test_v06_bilingual_pairs_are_structurally_aligned() -> None:
    report = audit_bilingual_pairs.build_report(
        EN_DIR,
        VI_DIR,
        categories=BILINGUAL_CATEGORIES,
        expected_pairs_per_category=BILINGUAL_RECORDS_PER_LANGUAGE,
    )

    assert report["valid"], report
    assert report["pair_count"] == 400
    assert report["physical_record_count"] == 800
    assert report["pair_violations"] == []


def test_v06_each_category_passes_exact_and_template_audits() -> None:
    checkpoint_report = audit_scenario_coverage.build_report(
        V06_DIR,
        expected_per_category=PHYSICAL_RECORDS_PER_CATEGORY,
        expected_categories=ALL_CATEGORIES,
        strict_list_items=True,
    )
    assert checkpoint_report["valid"], checkpoint_report
    assert checkpoint_report["scenario_count"] == CHECKPOINT_COUNT

    for language, source_dir in (("en", EN_DIR), ("vi", VI_DIR)):
        for path in sorted(source_dir.glob("*.jsonl")):
            category = path.stem
            expected = (
                BILINGUAL_RECORDS_PER_LANGUAGE
                if category in BILINGUAL_CATEGORIES
                else PHYSICAL_RECORDS_PER_CATEGORY
            )
            report = audit_scenario_coverage.build_report(
                path,
                expected_per_category=expected,
                expected_categories={category},
                strict_list_items=True,
            )
            assert report["valid"], (language, category, report)
            phrase_report = audit_template_phrases.build_report(path)
            assert phrase_report["candidate_count"] == 0, (
                language,
                category,
                phrase_report,
            )


def test_v06_lineage_and_review_manifests_cover_the_checkpoint() -> None:
    lineage = json.loads((V06_DIR / "lineage-index.json").read_text(encoding="utf-8"))

    assert lineage == generate_v06_lineage_index.build_index()
    assert lineage["scenario_count"] == CHECKPOINT_COUNT
    assert lineage["derivation_counts"] == {"adapted": 90, "authored_new": 1110}

    en_result = validate_review_manifest(EN_DIR, EN_DIR / "review-status.json")
    vi_result = validate_review_manifest(VI_DIR, VI_DIR / "review-status.json")
    assert en_result["valid"] is True
    assert en_result["scenario_count"] == 800
    assert en_result["status_counts"] == {"maintainer_reviewed": 800}
    assert en_result["culturally_reviewed_count"] == 0
    assert vi_result["valid"] is True
    assert vi_result["scenario_count"] == 400
    assert vi_result["status_counts"] == {"maintainer_reviewed": 400}
    assert vi_result["culturally_reviewed_count"] == 0

    for language in ("en", "vi"):
        manifest_path = V06_DIR / language / "review-status.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest == generate_v06_review_manifest.build_manifest(
            language, maintainer_review_all=True
        )


def test_v06_checkpoint_index_is_digest_bound_and_reproducible() -> None:
    index = json.loads((V06_DIR / "checkpoint-index.json").read_text(encoding="utf-8"))

    assert index == generate_v06_checkpoint_index.build_index()
    assert index["scenario_count"] == CHECKPOINT_COUNT
    assert index["category_count"] == 24
    assert index["language_counts"] == {"en": 800, "vi": 400}
    assert index["review_status_counts"] == {"maintainer_reviewed": 1200}


def test_v06_checkpoint_lexical_audits_are_clean_and_digest_bound() -> None:
    historical = [
        scenario
        for version in ("v0.1", "v0.2", "v0.3", "v0.4", "v0.5")
        for path in sorted((ROOT / "data" / "scenarios" / version).glob("*.jsonl"))
        for scenario in load_scenarios(path)
    ]
    historical_digest = audit_scenario_similarity.scenario_set_digest(historical)

    for language, expected_count, expected_authored_new in (
        ("en", 800, 726),
        ("vi", 400, 384),
    ):
        report = json.loads(
            (V06_DIR / f"checkpoint-lexical-similarity-audit-{language}.json").read_text(
                encoding="utf-8"
            )
        )
        scenarios = _load_language(language)
        assert report["scenario_count"] == expected_count
        assert report["authored_new_count"] == expected_authored_new
        assert report["historical_scenario_count"] == len(historical) == 688
        assert report["source_scenario_sha256"] == (
            audit_scenario_similarity.scenario_set_digest(scenarios)
        )
        assert report["comparison_scenario_sha256"] == historical_digest
        assert report["candidate_count"] == 0
        assert report["candidates"] == []
