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
)
from humanai_impact_bench.scoring import score_annotations
from humanai_impact_bench.validation import load_scenarios
from scripts import v07_artifacts
from scripts.audit_template_phrases import _ngrams
from scripts.v07_artifacts import single_tag

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = json.loads((ROOT / "configs/scenario-coverage-standard.json").read_text())
AGENTIC_EN = ROOT / "data/scenarios/v0.7/agentic/en"
AUTHORED_AGENTIC_CATEGORIES = {
    "cross_session_memory_governance",
    "personalized_persuasion_and_steering",
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
