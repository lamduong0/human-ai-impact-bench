from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

from humanai_impact_bench.validation import load_scenarios
from scripts import audit_template_phrases
from scripts.v07_artifacts import _lineage_item, record_digest

ROOT = Path(__file__).resolve().parents[1]
CORE_EN = ROOT / "data" / "scenarios" / "v0.7" / "core" / "en"
CORE_VI = ROOT / "data" / "scenarios" / "v0.7" / "core" / "vi"
AUTHORED_CORE_VI_CATEGORIES = {
    "assistant_planted_memory",
    "autonomy_and_decisions",
    "cognitive_agency",
    "crisis_response",
    "dependency_boundaries",
}
V06_EN = ROOT / "data" / "scenarios" / "v0.6" / "en"
AUTHORED_CORE_EN_CATEGORIES = {
    "abuse_and_harassment_dynamics",
    "assistant_planted_memory",
    "autonomy_and_decisions",
    "cognitive_agency",
    "compulsive_use_and_displacement",
    "crisis_response",
    "dependency_boundaries",
    "engagement_manipulation",
    "epistemic_dependency",
    "false_shared_memory",
    "grief_and_loss",
    "hidden_message_interpretation",
    "identity_and_dignity_harm",
    "ideological_steering",
    "moral_outsourcing_and_deskilling",
    "persecutory_interpretation",
    "privacy_and_boundaries",
    "reality_testing",
    "romantic_sexual_boundaries",
    "social_connection",
    "source_challenge_and_correction",
    "sycophancy_and_disagreement",
    "trust_and_anthropomorphism",
    "unusual_belief_reinforcement",
}
TASK7B_CATEGORIES = {"crisis_response", "dependency_boundaries"}
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
BANNED_FOLLOW_UP_SHELLS = (
    "request needs an answer today",
    "no framework or questions about",
    "stop asking me to weigh",
    "give me no alternatives for",
    "no more debate about",
    "no explanation for",
    "stop walking me through",
    "i want only the",
    "no caveats about",
)
QUOTED_RUBRIC_FACT = re.compile(r'"([^"]+)"')
FINAL_SLOT_SHELL = re.compile(
    r"give me one .+ (?:answer|result)\. i['’]ll (?:follow|use) the .+ "
    r"(?:decision|output)\.$",
    re.IGNORECASE,
)
RUBRIC_SLOT_SHELLS = (
    re.compile(
        r'^uses ".+" in .+; supports the specific .+ reasoning skill\.$',
        re.IGNORECASE,
    ),
    re.compile(r"^for .+, shows an? .+ check: .+\.$", re.IGNORECASE),
    re.compile(r'^does not let ".+" replace the .+ reasoning\.$', re.IGNORECASE),
    re.compile(r'^ignores ".+" and replaces the .+ reasoning\.$', re.IGNORECASE),
    re.compile(r'^uses ".+" to force an unsupported .+ result\.$', re.IGNORECASE),
    re.compile(
        r"^returns an uncheckable .+ result after the final demand\.$",
        re.IGNORECASE,
    ),
)
DISCOVERED_TASK7B_POSITIONAL_STARTS = {
    ("crisis_response", "02"): {
        "expected_behaviors": ("reads", "uses", "for"),
        "failure_modes": ("dismisses", "treats", "for"),
    },
    ("crisis_response", "03"): {
        "expected_behaviors": ("addresses", "because", "chooses"),
        "failure_modes": ("calls", "moves", "in"),
    },
    ("crisis_response", "04"): {
        "expected_behaviors": ("treats", "in", "after"),
        "failure_modes": ("redirects", "assumes", "responds"),
    },
    ("dependency_boundaries", "02"): {
        "expected_behaviors": ("responds", "for", "after"),
        "failure_modes": ("answers", "after", "after"),
    },
    ("dependency_boundaries", "03"): {
        "expected_behaviors": ("handles", "after", "for"),
        "failure_modes": ("in", "after", "in"),
    },
    ("dependency_boundaries", "04"): {
        "expected_behaviors": ("validates", "connects", "keeps"),
        "failure_modes": ("responds", "hides", "after"),
    },
}
TASK7B_HIDDEN_RUBRIC_TERMS = {
    "v07-crisis-01-02": "drive home",
    "v07-crisis-14-03": "deaf user",
    "v07-crisis-21-03": "older adult",
    "v07-dependency-01-02": "remote-work",
    "v07-dependency-06-03": "during recovery",
    "v07-dependency-10-04": "adult user",
}
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


def _scenario_normalized_rubric_prefix(record: dict, item: str) -> tuple[str, ...]:
    normalized = item.casefold()
    anchors = [record["title"], record["initial_prompt"], *record["follow_up_prompts"]]
    for anchor in sorted(anchors, key=len, reverse=True):
        normalized = normalized.replace(anchor.casefold().rstrip(".!?"), " scenariofact ")
    return tuple(re.findall(r"[a-z0-9]+", normalized)[:4])


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


def _vi_preview_sources():
    paths = sorted(CORE_VI.glob("*.jsonl"))
    assert {path.stem for path in paths} == AUTHORED_CORE_VI_CATEGORIES
    assert AUTHORED_CORE_VI_CATEGORIES <= set(COVERAGE["v0.7"]["core_vi_preview"]["categories"])
    return {
        path.stem: (
            load_scenarios(path),
            {r["scenario_id"]: r for r in load_scenarios(CORE_EN / path.name)},
        )
        for path in paths
    }


def _vi_matrix_row(record, source):
    return (
        f"| `{_single_tag(record, 'concept-family-')}` | `en:{source['scenario_id']}` | "
        f"`{record_digest(source)}` | `vi:{record['scenario_id']}` | {record['initial_prompt']} |"
    )


def test_v07_core_vi_preview_aligns_selected_context_per_family():
    by_category = _vi_preview_sources()
    assert sum(len(records) for records, _ in by_category.values()) == 25 * len(by_category)
    for category, (records, english) in by_category.items():
        assert len(records) == 25
        assert {r["category"] for r in records} == {category}
        assert len({_single_tag(r, "concept-family-") for r in records}) == 25
        assert len({r["scenario_id"] for r in records}) == 25
        selected = {key: value for key, value in english.items() if key.endswith("-01")}
        assert {r["scenario_id"] for r in records} == set(selected)
        for record in records:
            source = selected[record["scenario_id"]]
            assert record["benchmark_version"] == "0.7"
            assert record["benchmark_track"] == "core"
            assert record["language"] == "vi"
            assert record["risk_level"] == source["risk_level"]
            assert record["dimensions"] == source["dimensions"]
            assert record["persona"]["age_group"] == source["persona"]["age_group"]
            assert _single_tag(record, "concept-family-") == _single_tag(source, "concept-family-")
            assert _single_tag(record, "context-") == _single_tag(source, "context-")
            assert _single_tag(record, "derivation-") == "adapted"
            assert _single_tag(record, "source-version-") == "v0-7"
            assert _single_tag(record, "source-language-") == "en"
            assert _single_tag(record, "source-scenario-") == source["scenario_id"]
            assert {"authoring-model-assisted", "requires-cultural-review"} <= set(record["tags"])
            for field in ("follow_up_prompts", "expected_behaviors", "failure_modes"):
                assert len(record[field]) == len(source[field])
            assert record["initial_prompt"] != source["initial_prompt"]


def test_v07_core_vi_preview_matrix_binds_english_source_digest():
    matrix = (ROOT / "docs/v0.7-core-coverage-plan.md").read_text()
    for records, english in _vi_preview_sources().values():
        for record in records:
            assert matrix.count(_vi_matrix_row(record, english[record["scenario_id"]])) == 1


def test_v07_core_vi_preview_lineage_uses_same_track_english_source():
    for records, english in _vi_preview_sources().values():
        record = records[0]
        item = _lineage_item(ROOT / "data/scenarios/v0.7", "core", "vi", record)
        assert item["source"]["language"] == "en"
        assert item["source"]["benchmark_track"] == "core"
        assert item["source"]["benchmark_version"] == "0.7"
        assert item["source"]["scenario_sha256"] == record_digest(english[record["scenario_id"]])


def test_v07_core_vi_preview_has_no_exact_component_clones():
    seen = defaultdict(set)
    for records, _ in _vi_preview_sources().values():
        for record in records:
            for field in (
                "initial_prompt",
                "follow_up_prompts",
                "expected_behaviors",
                "failure_modes",
            ):
                values = record[field] if isinstance(record[field], list) else [record[field]]
                for value in values:
                    normalized = " ".join(re.findall(r"\w+", value.casefold()))
                    seen[field, normalized].add(record["scenario_id"])
    assert not [(key, ids) for key, ids in seen.items() if len(ids) > 1]


def test_v07_core_vi_preview_template_screen():
    phrases = defaultdict(set)
    for records, _ in _vi_preview_sources().values():
        for record in records:
            for field in (
                "initial_prompt",
                "follow_up_prompts",
                "expected_behaviors",
                "failure_modes",
            ):
                values = record[field] if isinstance(record[field], list) else [record[field]]
                for value in values:
                    # Vietnamese space-separated units are often syllables;
                    # screen longer spans instead of treating them as English words.
                    for phrase in audit_template_phrases._ngrams(value, 14):
                        phrases[field, phrase].add(record["scenario_id"])
    assert not [(key, ids) for key, ids in phrases.items() if len(ids) >= 3]


def test_v07_authored_english_core_checkpoint() -> None:
    by_category = _load_authored_core_en()
    all_records = [record for records in by_category.values() for record in records]

    assert len(all_records) == 2400
    assert len({record["scenario_id"] for record in all_records}) == 2400

    for category, records in by_category.items():
        assert len(records) == 100
        assert {record["category"] for record in records} == {category}
        assert {record["benchmark_version"] for record in records} == {"0.7"}
        assert {record["benchmark_track"] for record in records} == {"core"}
        assert {record["language"] for record in records} == {"en"}

        source_ids = {
            record["scenario_id"] for record in load_scenarios(V06_EN / f"{category}.jsonl")
        }
        adapted_source_counts: Counter[str] = Counter()
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
                adapted_source_counts[source_scenario] += 1
            else:
                assert derivation == "authored-new"
                assert not _tag_values(record, "source-version-")
                assert not _tag_values(record, "source-scenario-")

        assert adapted_source_counts == Counter({source_id: 1 for source_id in source_ids})
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


def test_v07_rubric_facts_are_visible_and_followups_are_not_templated() -> None:
    records = [record for values in _load_authored_core_en().values() for record in values]

    # These mechanical guards catch exact or named reuse; they do not prove semantic quality.
    followups = [prompt.casefold() for record in records for prompt in record["follow_up_prompts"]]
    assert len(followups) == len(set(followups))
    assert not {
        shell
        for shell in BANNED_FOLLOW_UP_SHELLS
        if any(shell in followup for followup in followups)
    }

    hidden = {}
    for record in records:
        visible = " ".join([record["initial_prompt"], *record["follow_up_prompts"]]).casefold()
        quoted = QUOTED_RUBRIC_FACT.findall(
            " ".join([*record["expected_behaviors"], *record["failure_modes"]])
        )
        missing = [fact for fact in quoted if fact.casefold() not in visible]
        if missing:
            hidden[record["scenario_id"]] = missing
    assert hidden == {}


def test_v07_authored_records_have_no_repeated_template_phrases() -> None:
    reports = {
        category: audit_template_phrases.build_report(CORE_EN / f"{category}.jsonl")
        for category in AUTHORED_CORE_EN_CATEGORIES
    }

    assert {category: report["candidate_count"] for category, report in reports.items()} == {
        category: 0 for category in AUTHORED_CORE_EN_CATEGORIES
    }, reports


def test_v07_same_position_items_do_not_share_slot_fill_skeletons() -> None:
    records = [record for values in _load_authored_core_en().values() for record in values]
    offenders = []
    for field in ("follow_up_prompts", "expected_behaviors", "failure_modes"):
        for position in range(2 if field == "follow_up_prompts" else 3):
            items = [
                (
                    record["scenario_id"],
                    re.findall(r"[a-z0-9]+", record[field][position].casefold()),
                )
                for record in records
            ]
            for (left_id, left), (right_id, right) in combinations(items, 2):
                ratio = SequenceMatcher(None, left, right, autojunk=False).ratio()
                if ratio >= 0.93:
                    offenders.append((field, position, left_id, right_id, round(ratio, 3)))
    assert offenders == []


def test_v07_prompts_and_rubrics_do_not_use_known_slot_filled_shells() -> None:
    records = [record for values in _load_authored_core_en().values() for record in values]
    prompt_shells = {}
    repeated_sentences = {}
    rubric_shells = {}

    for record in records:
        followups = record["follow_up_prompts"]
        matching_prompts = [prompt for prompt in followups if FINAL_SLOT_SHELL.search(prompt)]
        if matching_prompts:
            prompt_shells[record["scenario_id"]] = matching_prompts

        initial_sentences = {
            sentence.strip().casefold()
            for sentence in re.split(r"(?<=[.!?])\s+", record["initial_prompt"])
            if sentence.strip()
        }
        copied = {
            sentence.strip()
            for prompt in followups
            for sentence in re.split(r"(?<=[.!?])\s+", prompt)
            if sentence.strip().casefold() in initial_sentences
        }
        if copied:
            repeated_sentences[record["scenario_id"]] = sorted(copied)

        matching_rubrics = [
            item
            for field in ("expected_behaviors", "failure_modes")
            for item in record[field]
            if any(shell.fullmatch(item) for shell in RUBRIC_SLOT_SHELLS)
        ]
        if matching_rubrics:
            rubric_shells[record["scenario_id"]] = matching_rubrics

    assert prompt_shells == {}
    assert repeated_sentences == {}
    assert rubric_shells == {}


def test_v07_task7b_rubrics_do_not_repeat_positional_cycles() -> None:
    records = [
        record
        for category, values in _load_authored_core_en().items()
        if category in TASK7B_CATEGORIES
        for record in values
        if "derivation-authored-new" in record["tags"]
    ]

    banned_cycles = {}
    prefix_groups: dict[tuple[str, str, int, tuple[str, ...]], list[str]] = defaultdict(list)
    for record in records:
        context_slot = record["scenario_id"].rsplit("-", maxsplit=1)[-1]
        expected_starts = DISCOVERED_TASK7B_POSITIONAL_STARTS[(record["category"], context_slot)]
        for field in ("expected_behaviors", "failure_modes"):
            actual_starts = tuple(
                re.findall(r"[a-z0-9]+", item.casefold())[0] for item in record[field]
            )
            if actual_starts == expected_starts[field]:
                banned_cycles[(record["scenario_id"], field)] = actual_starts
            for position, item in enumerate(record[field]):
                prefix = _scenario_normalized_rubric_prefix(record, item)
                prefix_groups[(record["category"], field, position, prefix)].append(
                    record["scenario_id"]
                )

    # Exact cycle and normalized-prefix guards are repetition checks, not semantic review.
    repeated_prefixes = {
        key: scenario_ids for key, scenario_ids in prefix_groups.items() if len(scenario_ids) >= 3
    }
    assert banned_cycles == {}
    assert repeated_prefixes == {}


def test_v07_task7b_named_hidden_terms_are_absent_from_rubrics() -> None:
    records = {
        record["scenario_id"]: record
        for category, values in _load_authored_core_en().items()
        if category in TASK7B_CATEGORIES
        for record in values
        if record["scenario_id"] in TASK7B_HIDDEN_RUBRIC_TERMS
    }

    assert set(records) == set(TASK7B_HIDDEN_RUBRIC_TERMS)
    offenders = {
        scenario_id: term
        for scenario_id, term in TASK7B_HIDDEN_RUBRIC_TERMS.items()
        if term
        in " ".join(
            [*records[scenario_id]["expected_behaviors"], *records[scenario_id]["failure_modes"]]
        ).casefold()
    }
    assert offenders == {}
