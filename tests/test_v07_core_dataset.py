from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from humanai_impact_bench.validation import load_scenarios
from scripts import audit_template_phrases

ROOT = Path(__file__).resolve().parents[1]
CORE_EN = ROOT / "data" / "scenarios" / "v0.7" / "core" / "en"
V06_EN = ROOT / "data" / "scenarios" / "v0.6" / "en"
AUTHORED_CORE_EN_CATEGORIES = {
    "autonomy_and_decisions",
    "cognitive_agency",
}
INITIAL_RUBRIC_CUES = re.compile(
    r"\b(?:"
    r"without (?:asking|checking|explaining|showing|walking|making|identifying|verification)|"
    r"do not (?:want|ask|explain|check|read|reconsider|think|analy[sz]e)|"
    r"never (?:have to|check|read|learn|write)|"
    r"skip (?:the|more|any|questions|planning|review)|"
    r"no reasoning|stop updating|stop me reconsidering|hide the|"
    r"leave out|ignore (?:the )?(?:other|contrary)|before I (?:estimate|try)"
    r"|tell me not to (?:think|reconsider)"
    r")\b",
    re.IGNORECASE,
)
FIRST_FOLLOW_UP_PRESSURE = re.compile(
    r"\b(?:now|today|tonight|soon|before|deadline|waiting|already|due|expires?|"
    r"appointment|meeting|week|hour|need|want|must|just|only|direct|answer|"
    r"choose|decide|confirm)\b",
    re.IGNORECASE,
)
FINAL_FOLLOW_UP_RESISTANCE = re.compile(
    r"\b(?:do not|don't|stop|no |only|just|must|will follow|i need|i want|"
    r"tell me|give me|choose|decide|answer|confirm|promise|sign|send|use|buy|"
    r"accept|reject|follow)\b",
    re.IGNORECASE,
)
COVERAGE = json.loads(
    (ROOT / "configs" / "scenario-coverage-standard.json").read_text(encoding="utf-8")
)


def _tag_values(record: dict, prefix: str) -> list[str]:
    return [tag.removeprefix(prefix) for tag in record["tags"] if tag.startswith(prefix)]


def _single_tag(record: dict, prefix: str) -> str:
    values = _tag_values(record, prefix)
    assert len(values) == 1 and values[0], (
        f"{record['scenario_id']} must have exactly one non-empty {prefix} tag"
    )
    return values[0]


def _load_authored_core_en() -> dict[str, list[dict]]:
    paths = sorted(CORE_EN.glob("*.jsonl"))
    assert {path.stem for path in paths} == AUTHORED_CORE_EN_CATEGORIES
    return {path.stem: load_scenarios(path) for path in paths}


def test_v07_core_english_coverage_arithmetic() -> None:
    core = COVERAGE["v0.7"]["core_en"]

    assert core["category_count"] == 24
    assert core["concept_families_per_category"] == 25
    assert core["contexts_per_family"] == 4
    assert core["records_per_category"] == 100
    assert core["total_records"] == 2400


def test_v07_core_vietnamese_preview_scope() -> None:
    preview = COVERAGE["v0.7"]["core_vi_preview"]

    assert preview["category_count"] == 16
    assert preview["records_per_category"] == 25
    assert preview["total_records"] == 400
    assert preview["blocks_english_milestone"] is False


def test_v07_authored_english_core_checkpoint() -> None:
    by_category = _load_authored_core_en()
    all_records = [record for records in by_category.values() for record in records]

    assert len(all_records) == 200
    assert len({record["scenario_id"] for record in all_records}) == 200

    for category, records in by_category.items():
        assert len(records) == 100
        assert {record["category"] for record in records} == {category}
        assert {record["benchmark_version"] for record in records} == {"0.7"}
        assert {record["benchmark_track"] for record in records} == {"core"}
        assert {record["language"] for record in records} == {"en"}

        source_ids = {
            record["scenario_id"] for record in load_scenarios(V06_EN / f"{category}.jsonl")
        }
        adapted_source_ids: set[str] = set()
        contexts_by_family: dict[str, set[str]] = defaultdict(set)
        for record in records:
            assert len(record["follow_up_prompts"]) >= 2
            assert len(record["expected_behaviors"]) >= 2
            assert len(record["failure_modes"]) >= 2
            assert "authoring-model-assisted" in record["tags"]

            family = _single_tag(record, "concept-family-")
            contexts_by_family[family].add(_single_tag(record, "context-"))
            derivation = _single_tag(record, "derivation-")
            if derivation == "adapted":
                assert _tag_values(record, "source-version-") == ["v0-6"]
                source_scenario = _single_tag(record, "source-scenario-")
                assert source_scenario in source_ids
                adapted_source_ids.add(source_scenario)
            else:
                assert derivation == "authored-new"
                assert not _tag_values(record, "source-version-")
                assert not _tag_values(record, "source-scenario-")

        assert adapted_source_ids == source_ids
        assert len(contexts_by_family) == 25
        assert all(len(contexts) == 4 for contexts in contexts_by_family.values())


def test_v07_initial_prompts_do_not_announce_the_rubric() -> None:
    records = [record for values in _load_authored_core_en().values() for record in values]

    leaked = {
        record["scenario_id"]: record["initial_prompt"]
        for record in records
        if INITIAL_RUBRIC_CUES.search(record["initial_prompt"])
    }
    assert leaked == {}


def test_v07_followups_have_visible_pressure_and_resistance_anchors() -> None:
    records = [record for values in _load_authored_core_en().values() for record in values]

    missing_first = {
        record["scenario_id"]: record["follow_up_prompts"][0]
        for record in records
        if not FIRST_FOLLOW_UP_PRESSURE.search(record["follow_up_prompts"][0])
    }
    missing_final = {
        record["scenario_id"]: record["follow_up_prompts"][-1]
        for record in records
        if not FINAL_FOLLOW_UP_RESISTANCE.search(record["follow_up_prompts"][-1])
    }
    assert missing_first == {}
    assert missing_final == {}


def test_v07_authored_records_have_no_repeated_template_phrases() -> None:
    reports = {
        category: audit_template_phrases.build_report(CORE_EN / f"{category}.jsonl")
        for category in AUTHORED_CORE_EN_CATEGORIES
    }

    assert {category: report["candidate_count"] for category, report in reports.items()} == {
        category: 0 for category in AUTHORED_CORE_EN_CATEGORIES
    }, reports
