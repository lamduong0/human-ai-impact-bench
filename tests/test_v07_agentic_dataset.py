"""Planned agentic coverage and provisional scoring hooks, not corpus maturity."""

import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

import pytest

from humanai_impact_bench.constants import (
    AUTOMATIC_SAFETY_FAILURES,
    CRITICAL_FAILURE_DEFINITIONS,
    CRITICAL_FAILURE_PENALTIES,
    V07_CATEGORIES,
)
from humanai_impact_bench.scoring import score_annotations
from humanai_impact_bench.validation import load_scenarios
from scripts import v07_artifacts
from scripts.audit_template_phrases import _ngrams
from scripts.v07_artifacts import _lineage_item, record_digest, single_tag

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = json.loads((ROOT / "configs/scenario-coverage-standard.json").read_text())
AGENTIC_EN = ROOT / "data/scenarios/v0.7/agentic/en"
AGENTIC_VI = ROOT / "data/scenarios/v0.7/agentic/vi"
AUTHORED_AGENTIC_CATEGORIES = {
    "cross_session_memory_governance",
    "delegated_action_authorization",
    "personalized_persuasion_and_steering",
    "trajectory_recovery_and_correction",
}


def _records():
    paths = sorted(AGENTIC_EN.glob("*.jsonl"))
    assert {path.stem for path in paths} == AUTHORED_AGENTIC_CATEGORIES
    return [record for path in paths for record in load_scenarios(path)]


def _pairs():
    pairs = defaultdict(list)
    for record in _records():
        pairs[record["matched_pair_id"]].append(record)
    return pairs


def test_authored_agentic_checkpoint():
    records = _records()
    assert AUTHORED_AGENTIC_CATEGORIES == V07_CATEGORIES
    assert len(records) == COVERAGE["v0.7"]["agentic_en"]["total_records"] == 400
    assert len(records) == 100 * len(AUTHORED_AGENTIC_CATEGORIES)
    assert len({r["scenario_id"] for r in records}) == len(records)
    assert Counter(r["category"] for r in records) == dict.fromkeys(
        AUTHORED_AGENTIC_CATEGORIES, 100
    )
    families = defaultdict(lambda: defaultdict(set))
    for record in records:
        assert record["benchmark_version"] == "0.7"
        assert record["benchmark_track"] == "agentic"
        assert record["language"] == "en" and record["locale"] == "en-US"
        assert record["persona"]["age_group"] == "adult"
        assert single_tag(record, "locale-") == "en-us"
        assert single_tag(record, "protocol-") == record["protocol_mode"].replace("_", "-")
        assert single_tag(record, "derivation-") == "authored-new"
        assert "authoring-model-assisted" in record["tags"]
        assert not any(
            t.startswith(("source-version-", "source-scenario-")) for t in record["tags"]
        )
        family = single_tag(record, "concept-family-")
        families[record["category"]][family].add(single_tag(record, "context-"))
        assert len(record["follow_up_prompts"]) == 2
        assert len(record["expected_behaviors"]) >= 2
        assert len(record["failure_modes"]) >= 2
        required_dimensions = {
            "cross_session_memory_governance": {"memory_integrity", "trust_calibration"},
            "personalized_persuasion_and_steering": {"autonomy_support", "non_sycophancy"},
            "delegated_action_authorization": {"autonomy_support", "trust_calibration"},
            "trajectory_recovery_and_correction": {"correction_responsiveness"},
        }
        assert required_dimensions[record["category"]] <= set(record["dimensions"])
    for category_families in families.values():
        assert len(category_families) == 25
        assert all(len(contexts) == 2 for contexts in category_families.values())


def test_agentic_pairs_hold_all_controlled_fields_exactly():
    pairs = _pairs()
    assert len(pairs) == 50 * len(AUTHORED_AGENTIC_CATEGORIES)
    contexts = set()
    for pair_id, members in pairs.items():
        assert len(members) == 2, pair_id
        assert {r["protocol_mode"] for r in members} == {"control", "prefill_stress"}
        controlled = []
        for record in members:
            controlled.append(
                {
                    key: (
                        [t for t in value if not t.startswith("protocol-")]
                        if key == "tags"
                        else value
                    )
                    for key, value in record.items()
                    if key
                    not in {
                        "scenario_id",
                        "protocol_mode",
                        "prefill_messages",
                        "_source_line",
                        "_source_path",
                    }
                }
            )
        assert controlled[0] == controlled[1], pair_id
        context = single_tag(members[0], "context-")
        assert context not in contexts, context
        contexts.add(context)
        control = next(r for r in members if r["protocol_mode"] == "control")
        stress = next(r for r in members if r["protocol_mode"] == "prefill_stress")
        assert "prefill_messages" not in control
        history = stress["prefill_messages"]
        assert len(history) in {2, 4}
        assert [m["role"] for m in history] == ["user", "assistant"] * (len(history) // 2)


def test_agentic_exact_component_reuse_is_confined_to_matched_pairs():
    seen = defaultdict(set)
    for record in _records():
        for field in ("initial_prompt", "follow_up_prompts", "expected_behaviors", "failure_modes"):
            values = record[field] if isinstance(record[field], list) else [record[field]]
            for value in values:
                normalized = " ".join(re.findall(r"\w+", value.casefold()))
                seen[field, normalized].add(record["matched_pair_id"])
    assert not [(key, ids) for key, ids in seen.items() if len(ids) > 1]


def test_agentic_pair_aware_template_audit():
    phrases = defaultdict(set)
    for pair_id, members in _pairs().items():
        record = members[0]
        for field in ("initial_prompt", "follow_up_prompts", "expected_behaviors", "failure_modes"):
            values = record[field] if isinstance(record[field], list) else [record[field]]
            for value in values:
                for phrase in _ngrams(value, 7):
                    phrases[field, phrase].add(pair_id)
    assert not [(key, ids) for key, ids in phrases.items() if len(ids) >= 3]


def test_agentic_distinct_pairs_do_not_share_near_identical_prompt_bundles():
    bundles = []
    for pair_id, members in _pairs().items():
        record = members[0]
        tokens = re.findall(
            r"\w+", " ".join([record["initial_prompt"], *record["follow_up_prompts"]]).casefold()
        )
        bundles.append((pair_id, tokens))
    close_pairs = []
    for (left_id, left), (right_id, right) in combinations(bundles, 2):
        similarity = SequenceMatcher(None, left, right, autojunk=False).ratio()
        if similarity >= 0.85:
            close_pairs.append((left_id, right_id, similarity))
    assert not close_pairs


def _matrix_cell(control, stress):
    history = " / ".join(f"{m['role']}: {m['content']}" for m in stress["prefill_messages"])
    return (
        f"`{control['matched_pair_id']}`; `{single_tag(control, 'context-')}`. "
        f"Visible: {control['initial_prompt']} Next: {control['follow_up_prompts'][0]} "
        f"Then: {control['follow_up_prompts'][1]} Stress history: {history} "
        f"Risk: {control['risk_level']}. Dimensions: {', '.join(control['dimensions'])}. "
        "Lineage: authored-new."
    )


def test_agentic_coverage_matrix_matches_every_pair():
    matrix = (ROOT / "docs/v0.7-agentic-research-plan.md").read_text()
    for members in _pairs().values():
        control = next(r for r in members if r["protocol_mode"] == "control")
        stress = next(r for r in members if r["protocol_mode"] == "prefill_stress")
        assert matrix.count(_matrix_cell(control, stress)) == 1


def test_authored_agentic_families_and_pairs_stay_in_one_split(monkeypatch):
    records = _records()
    # Other language/track configurations are outside this partial checkpoint.
    # Only inventory loading is substituted; exercise the real split assignment.
    monkeypatch.setattr(v07_artifacts, "_configurations", lambda root: [("agentic", "en", records)])
    index = v07_artifacts.build_split_index()
    by_id = {item["scenario_id"]: item["split"] for item in index["items"]}
    assert set(by_id) == {r["scenario_id"] for r in records}
    families = defaultdict(set)
    pairs = defaultdict(set)
    category_splits = defaultdict(Counter)
    for record in records:
        split = by_id[record["scenario_id"]]
        families[single_tag(record, "concept-family-")].add(split)
        pairs[record["matched_pair_id"]].add(split)
        category_splits[record["category"]][split] += 1
    assert all(len(splits) == 1 for splits in families.values())
    assert all(len(splits) == 1 for splits in pairs.values())
    assert all(
        counts == {"calibration": 80, "public_evaluation": 20}
        for counts in category_splits.values()
    )


def test_v07_agentic_coverage_arithmetic():
    en = COVERAGE["v0.7"]["agentic_en"]
    assert en == {
        "category_count": 4,
        "concept_families_per_category": 25,
        "contexts_per_family": 2,
        "protocol_modes": ["control", "prefill_stress"],
        "records_per_category": 100,
        "total_records": 400,
    }
    assert (
        en["concept_families_per_category"] * en["contexts_per_family"] * len(en["protocol_modes"])
        == en["records_per_category"]
    )
    assert en["category_count"] * en["records_per_category"] == en["total_records"]


def test_v07_agentic_vietnamese_preview_arithmetic():
    vi = COVERAGE["v0.7"]["agentic_vi_preview"]
    assert vi == {
        "category_count": 4,
        "concept_families_per_category": 25,
        "contexts_per_family": 1,
        "protocol_modes": ["control", "prefill_stress"],
        "records_per_category": 50,
        "total_records": 200,
        "blocks_english_milestone": False,
    }
    assert (
        vi["concept_families_per_category"] * vi["contexts_per_family"] * len(vi["protocol_modes"])
        == vi["records_per_category"]
    )
    assert vi["category_count"] * vi["records_per_category"] == vi["total_records"]


def test_action_authorization_violation_is_registered():
    label = "action_authorization_violation"
    assert label in CRITICAL_FAILURE_PENALTIES
    assert CRITICAL_FAILURE_PENALTIES[label] == 40.0
    assert "authorization" in CRITICAL_FAILURE_DEFINITIONS[label].lower()
    assert label in AUTOMATIC_SAFETY_FAILURES


@pytest.mark.parametrize("has_violation", [False, True])
def test_action_authorization_scoring_hook(annotation_factory, has_violation):
    label = "action_authorization_violation"
    annotations = [
        annotation_factory(
            benchmark_version="0.7",
            benchmark_track="agentic",
            scenario_id=f"authorization-{index}",
            scores={"autonomy_support": 5, "trust_calibration": 5},
            critical_failures=[label, label] if has_violation and index == 0 else [],
        )
        for index in range(2)
    ]

    result = score_annotations(annotations)[0]

    assert result.base_score == 100.0
    assert result.total_penalty == (40.0 if has_violation else 0.0)
    assert result.penalty == (20.0 if has_violation else 0.0)
    assert result.penalty_events == (1 if has_violation else 0)
    assert result.overall_score == (80.0 if has_violation else 100.0)
    assert result.critical_failure_counts == ({label: 1} if has_violation else {})
    assert result.safety_pass is (not has_violation)


def _vi_preview():
    paths = sorted(AGENTIC_VI.glob("*.jsonl"))
    assert {path.stem for path in paths} == V07_CATEGORIES
    return [record for path in paths for record in load_scenarios(path)]


def _vi_pairs():
    pairs = defaultdict(list)
    for record in _vi_preview():
        pairs[record["matched_pair_id"]].append(record)
    return pairs


def _english_selected():
    return {
        record["scenario_id"]: record
        for record in _records()
        if record["matched_pair_id"].endswith("-01-en-us")
    }


def _vi_pair_matrix_row(control, stress, english):
    source_control = english[single_tag(control, "source-scenario-")]
    source_stress = english[single_tag(stress, "source-scenario-")]
    history = " / ".join(f"{m['role']}: {m['content']}" for m in stress["prefill_messages"])
    text = (
        (
            f"Visible: {control['initial_prompt']} Next: {control['follow_up_prompts'][0]} "
            f"Then: {control['follow_up_prompts'][1]} Stress history: {history} "
            f"Expected: {' / '.join(control['expected_behaviors'])} "
            f"Failures: {' / '.join(control['failure_modes'])} "
            f"Risk: {control['risk_level']}. Dimensions: {', '.join(control['dimensions'])}."
        )
        .replace("|", "\\|")
        .replace("\n", " ")
    )
    return (
        f"| `{single_tag(control, 'concept-family-')}` | `{control['matched_pair_id']}` | "
        f"control `{source_control['scenario_id']}` `{record_digest(source_control)}`; "
        f"stress `{source_stress['scenario_id']}` `{record_digest(source_stress)}` | "
        f"control `{control['scenario_id']}` `{record_digest(control)}`; "
        f"stress `{stress['scenario_id']}` `{record_digest(stress)}` | {text} |"
    )


def test_vi_preview_coverage_and_selected_english_lineage():
    records = _vi_preview()
    english = _english_selected()
    assert len(records) == len(english) == 200
    assert len({r["scenario_id"] for r in records}) == 200
    assert Counter(r["category"] for r in records) == dict.fromkeys(V07_CATEGORIES, 50)
    assert Counter(single_tag(r, "source-scenario-") for r in records) == dict.fromkeys(english, 1)
    families = defaultdict(lambda: defaultdict(set))
    for record in records:
        source = english[single_tag(record, "source-scenario-")]
        assert record["benchmark_version"] == "0.7"
        assert record["benchmark_track"] == "agentic"
        assert record["language"] == "vi" and record["locale"] == "vi-VN"
        assert single_tag(record, "locale-") == "vi-VN"
        assert record["scenario_id"] == source["scenario_id"].replace("-en-us-", "-vi-vn-")
        assert (
            record["matched_pair_id"] == source["matched_pair_id"].removesuffix("en-us") + "vi-vn"
        )
        assert single_tag(record, "derivation-") == "adapted"
        assert single_tag(record, "source-version-") == "v0-7"
        assert single_tag(record, "source-language-") == "en"
        assert {"requires-cultural-review", "authoring-model-assisted"} <= set(record["tags"])
        assert single_tag(record, "protocol-") == record["protocol_mode"].replace("_", "-")
        for field in ("category", "risk_level", "dimensions", "protocol_mode"):
            assert record[field] == source[field]
        assert record["persona"]["age_group"] == source["persona"]["age_group"] == "adult"
        for prefix in ("concept-family-", "context-"):
            assert single_tag(record, prefix) == single_tag(source, prefix)
        for field in ("follow_up_prompts", "expected_behaviors", "failure_modes"):
            assert len(record[field]) == len(source[field])
            assert record[field] != source[field]
        assert record["initial_prompt"] != source["initial_prompt"]
        families[record["category"]][single_tag(record, "concept-family-")].add(
            single_tag(record, "context-")
        )
        if record["protocol_mode"] == "control":
            assert "prefill_messages" not in record
        else:
            messages = record["prefill_messages"]
            assert len(messages) == len(source["prefill_messages"])
            assert len(messages) in {2, 4}
            assert [m["role"] for m in messages] == ["user", "assistant"] * (len(messages) // 2)
            for message, original in zip(messages, source["prefill_messages"], strict=True):
                assert message["role"] == original["role"]
                assert message["content"] != original["content"]
    assert all(len(category_families) == 25 for category_families in families.values())
    assert all(
        len(contexts) == 1
        for category_families in families.values()
        for contexts in category_families.values()
    )


def test_vi_preview_pair_common_fields_and_rubrics_are_identical():
    pairs = _vi_pairs()
    assert len(pairs) == 100
    for pair_id, members in pairs.items():
        assert len(members) == 2, pair_id
        assert {r["protocol_mode"] for r in members} == {"control", "prefill_stress"}
        controlled = [
            {
                key: (
                    [t for t in value if not t.startswith(("protocol-", "source-scenario-"))]
                    if key == "tags"
                    else value
                )
                for key, value in record.items()
                if key
                not in {
                    "scenario_id",
                    "protocol_mode",
                    "prefill_messages",
                    "_source_line",
                    "_source_path",
                }
            }
            for record in members
        ]
        assert controlled[0] == controlled[1], pair_id


def test_vi_preview_exact_digest_and_text_matrix():
    matrix = (ROOT / "docs/v0.7-agentic-research-plan.md").read_text()
    english = _english_selected()
    for members in _vi_pairs().values():
        control = next(r for r in members if r["protocol_mode"] == "control")
        stress = next(r for r in members if r["protocol_mode"] == "prefill_stress")
        assert matrix.count(_vi_pair_matrix_row(control, stress, english)) == 1


def test_vi_preview_pair_aware_text_audits():
    exact = defaultdict(set)
    phrases = defaultdict(set)
    for pair_id, members in _vi_pairs().items():
        record = members[0]
        for field in ("initial_prompt", "follow_up_prompts", "expected_behaviors", "failure_modes"):
            values = record[field] if isinstance(record[field], list) else [record[field]]
            for value in values:
                exact[field, " ".join(re.findall(r"\w+", value.casefold()))].add(pair_id)
                for phrase in _ngrams(value, 14):
                    phrases[field, phrase].add(pair_id)
    assert not [(key, ids) for key, ids in exact.items() if len(ids) > 1]
    assert not [(key, ids) for key, ids in phrases.items() if len(ids) >= 3]


def test_vi_preview_resolves_same_track_english_sources():
    english = _english_selected()
    for members in _vi_pairs().values():
        for record in members:
            item = _lineage_item(ROOT / "data/scenarios/v0.7", "agentic", "vi", record)
            source = english[single_tag(record, "source-scenario-")]
            assert item["source"]["benchmark_track"] == "agentic"
            assert item["source"]["language"] == "en"
            assert item["source"]["scenario_id"] == source["scenario_id"]
            assert item["source"]["scenario_sha256"] == record_digest(source)


def test_vi_preview_families_and_pairs_share_english_split(monkeypatch):
    english = _records()
    vietnamese = _vi_preview()
    monkeypatch.setattr(
        v07_artifacts,
        "_configurations",
        lambda root: [("agentic", "en", english), ("agentic", "vi", vietnamese)],
    )
    index = v07_artifacts.build_split_index()
    families = defaultdict(set)
    pair_splits = defaultdict(set)
    records = {(r["language"], r["scenario_id"]): r for r in [*english, *vietnamese]}
    assert index["scenario_count"] == 600
    assert index["split_counts"] == {"calibration": 480, "public_evaluation": 120}
    for item in index["items"]:
        record = records[item["language"], item["scenario_id"]]
        families[item["concept_family_id"]].add(item["split"])
        pair_splits[record["matched_pair_id"]].add(item["split"])
    assert all(len(splits) == 1 for splits in families.values())
    assert all(len(splits) == 1 for splits in pair_splits.values())
