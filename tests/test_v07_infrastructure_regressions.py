"""Adversarial checks for v0.7 evidence and configuration trust boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as SchemaError

from humanai_impact_bench.deployment import draft_evaluate, run_scenarios
from humanai_impact_bench.review import derive_review_status, scenario_digest
from humanai_impact_bench.scoring import score_annotations
from humanai_impact_bench.validation import ValidationError, validate_scenario
from scripts.v07_artifacts import _validate_overlap_audit, record_digest, scenario_set_digest

ROOT = Path(__file__).resolve().parents[1]


def review_event(scenario, **overrides):
    event = {
        "review_type": "construct",
        "reviewer_id": "reviewer-a",
        "qualification": "Declared construct reviewer",
        "decision": "approved",
        "reviewed_at": "2026-09-07T00:00:00Z",
        "conflict_disclosure": "no author conflict",
        "reviewed_locale": "en-US",
        "notes": "Synthetic test review; not corpus approval.",
        "scenario_digest": scenario_digest(scenario),
    }
    return event | overrides


def test_other_reviewer_cannot_erase_unresolved_objection(scenario_factory):
    scenario = scenario_factory(benchmark_version="0.7", benchmark_track="core", risk_level="low")
    events = [
        review_event(scenario, decision="changes_requested"),
        review_event(scenario, reviewer_id="reviewer-b", reviewed_at="2026-09-08T00:00:00Z"),
    ]
    assert derive_review_status(scenario, events) == "changes_requested"


def test_freeform_no_conflict_does_not_establish_author_independence(scenario_factory):
    scenario = scenario_factory(benchmark_version="0.7", benchmark_track="core", risk_level="low")
    assert derive_review_status(scenario, [review_event(scenario)]) == "in_review"


def test_reviewer_id_padding_cannot_bypass_declared_author_conflict(scenario_factory):
    scenario = scenario_factory(benchmark_version="0.7", benchmark_track="core", risk_level="low")
    with pytest.raises(ValidationError, match="reviewer_id"):
        derive_review_status(
            scenario, [review_event(scenario, reviewer_id="reviewer-a ")], author_ids=["reviewer-a"]
        )


def test_overlap_malformed_decision_fails_with_validation_error(scenario_factory):
    audit, configurations = overlap_fixture(scenario_factory)
    audit["resolutions"][0]["decision"] = []
    with pytest.raises(ValidationError, match="overlap"):
        _validate_overlap_audit(audit, configurations)


def test_declared_author_cannot_approve_own_construct_even_with_no_conflict_text(scenario_factory):
    scenario = scenario_factory(benchmark_version="0.7", benchmark_track="core", risk_level="low")
    assert (
        derive_review_status(scenario, [review_event(scenario)], author_ids=["reviewer-a"])
        == "in_review"
    )


def test_only_same_reviewer_and_scope_can_resolve_their_objection(scenario_factory):
    scenario = scenario_factory(benchmark_version="0.7", benchmark_track="core", risk_level="low")
    events = [
        review_event(scenario, decision="changes_requested"),
        review_event(scenario, reviewer_id="reviewer-b", reviewed_at="2026-09-08T00:00:00Z"),
        review_event(scenario, reviewed_locale="en-VN", reviewed_at="2026-09-09T00:00:00Z"),
    ]
    assert derive_review_status(scenario, events, author_ids=["author"]) == "changes_requested"
    events.append(review_event(scenario, reviewed_at="2026-09-10T00:00:00Z"))
    assert derive_review_status(scenario, events, author_ids=["author"]) == "reviewed"


def test_specialist_tag_requires_review_even_at_moderate_risk(scenario_factory):
    scenario = scenario_factory(
        benchmark_version="0.7",
        benchmark_track="core",
        risk_level="moderate",
        tags=["requires-specialist-review"],
    )
    events = [review_event(scenario)]
    assert derive_review_status(scenario, events, author_ids=["author"]) == "in_review"
    events.append(review_event(scenario, review_type="specialist_safety"))
    assert derive_review_status(scenario, events, author_ids=["author"]) == "reviewed"


@pytest.mark.parametrize("timestamp", ["2026-9-7T00:00:00Z", "2026-09-07T00:00:00.1Z"])
def test_review_timestamp_uses_exact_utc_seconds_in_runtime_and_schema(scenario_factory, timestamp):
    scenario = scenario_factory(benchmark_version="0.7", benchmark_track="core", risk_level="low")
    event = review_event(scenario, reviewed_at=timestamp)
    with pytest.raises(ValidationError, match="UTC timestamp"):
        derive_review_status(scenario, [event])
    schema = json.loads((ROOT / "schemas/review-status-v0.2.schema.json").read_text())
    with pytest.raises(SchemaError):
        Draft202012Validator(
            schema["$defs"]["review_event"], format_checker=FormatChecker()
        ).validate(event)


@pytest.mark.parametrize(
    ("track", "category"),
    [
        ("core", "delegated_action_authorization"),
        ("agentic", "dependency_boundaries"),
        ("core", "memory_consent_and_personalization"),
        ("core", "minor_safety"),
        ("core", "emotional_attunement"),
    ],
)
def test_v07_track_excludes_categories_outside_its_defined_instrument(
    scenario_factory, track, category
):
    fields = {"benchmark_version": "0.7", "benchmark_track": track, "category": category}
    if track == "agentic":
        fields.update(locale="en-US", protocol_mode="control", matched_pair_id="example-pair")
    scenario = scenario_factory(**fields)
    with pytest.raises(ValidationError, match="category"):
        validate_scenario(scenario)


@pytest.mark.parametrize(
    ("track", "category"),
    [
        ("core", "delegated_action_authorization"),
        ("agentic", "dependency_boundaries"),
        ("core", "memory_consent_and_personalization"),
        ("core", "minor_safety"),
        ("core", "emotional_attunement"),
    ],
)
def test_v07_schema_rejects_the_same_cross_instrument_categories(scenario_factory, track, category):
    fields = {"benchmark_version": "0.7", "benchmark_track": track, "category": category}
    if track == "agentic":
        fields.update(locale="en-US", protocol_mode="control", matched_pair_id="example-pair")
    schema = json.loads((ROOT / "schemas/scenario.schema.json").read_text())
    with pytest.raises(SchemaError):
        Draft202012Validator(schema).validate(scenario_factory(**fields))


def overlap_fixture(scenario_factory):
    records = [
        scenario_factory(
            benchmark_version="0.7", benchmark_track="core", scenario_id=f"overlap-{i}"
        )
        for i in (1, 2)
    ]
    content = {
        "kind": "lexical_overlap",
        "members": ["0.7/core/en/overlap-1", "0.7/core/en/overlap-2"],
        "evidence": "A repeated phrase requires an explicit disposition.",
    }
    candidate = {"candidate_id": record_digest(content), **content}
    resolution = {
        "candidate_id": candidate["candidate_id"],
        "decision": "accepted_distinct",
        "rationale": "Different decisions and consequences; retain both.",
    }
    audit = {
        "audit_version": "0.1",
        "benchmark_version": "0.7",
        "scenario_count": 2,
        "configuration_sha256": {"v0.7-core-en": scenario_set_digest(records)},
        "candidate_count": 1,
        "candidates": [candidate],
        "resolutions": [resolution],
        "valid": True,
    }
    return audit, [("core", "en", records)]


@pytest.mark.parametrize(
    "defect",
    [
        "null",
        "wrong_id",
        "missing_rationale",
        "unknown_decision",
        "duplicate",
        "extra",
        "missing",
        "candidate_hash",
        "duplicate_member",
        "missing_member",
        "candidate_duplicate",
    ],
)
def test_overlap_freeze_requires_exact_content_bound_dispositions(scenario_factory, defect):
    audit, configurations = overlap_fixture(scenario_factory)
    if defect == "null":
        audit["resolutions"] = [None]
    elif defect == "wrong_id":
        audit["resolutions"][0]["candidate_id"] = "b" * 64
    elif defect == "missing_rationale":
        audit["resolutions"][0]["rationale"] = " "
    elif defect == "unknown_decision":
        audit["resolutions"][0]["decision"] = "approved_whatever"
    elif defect in {"duplicate", "extra"}:
        audit["resolutions"].append(dict(audit["resolutions"][0]))
        if defect == "extra":
            audit["resolutions"][1]["candidate_id"] = "b" * 64
    elif defect == "missing":
        audit["resolutions"] = []
    elif defect == "candidate_hash":
        audit["candidates"][0]["candidate_id"] = "c" * 64
        audit["resolutions"][0]["candidate_id"] = "c" * 64
    elif defect in {"duplicate_member", "missing_member"}:
        candidate = audit["candidates"][0]
        candidate["members"][1] = (
            candidate["members"][0] if defect == "duplicate_member" else "0.7/core/en/absent"
        )
        candidate["members"].sort()
        candidate["candidate_id"] = record_digest(
            {key: value for key, value in candidate.items() if key != "candidate_id"}
        )
        audit["resolutions"][0]["candidate_id"] = candidate["candidate_id"]
    else:
        audit["candidate_count"] = 2
        audit["candidates"] *= 2
        audit["resolutions"] *= 2
    with pytest.raises(ValidationError, match="overlap"):
        _validate_overlap_audit(audit, configurations)


def test_overlap_freeze_accepts_valid_disposition_but_rejects_stale_corpus(scenario_factory):
    audit, configurations = overlap_fixture(scenario_factory)
    _validate_overlap_audit(audit, configurations)
    configurations[0][2][0]["initial_prompt"] = "A later revision changes the audited content."
    with pytest.raises(ValidationError, match="current scenarios"):
        _validate_overlap_audit(audit, configurations)


@pytest.mark.parametrize("validate", [True, False])
def test_scoring_never_combines_v07_tracks_even_for_prevalidated_rows(annotation_factory, validate):
    rows = [
        annotation_factory(
            scenario_id="core-record", benchmark_version="0.7", benchmark_track="core"
        ),
        annotation_factory(
            scenario_id="agentic-record", benchmark_version="0.7", benchmark_track="agentic"
        ),
    ]
    with pytest.raises(ValidationError, match="mixed.*track"):
        score_annotations(rows, validate=validate)


@pytest.mark.parametrize(
    "metadata",
    [
        {"benchmark_version": "0.7"},
        {"benchmark_track": "core"},
        {"benchmark_version": "0.7", "benchmark_track": "unknown"},
        {"scenario_id": "v07-known-source"},
    ],
)
def test_scoring_rejects_missing_or_invalid_v07_provenance(annotation_factory, metadata):
    with pytest.raises(ValidationError, match="provenance|benchmark_track|benchmark_version"):
        score_annotations([annotation_factory(**metadata)])


def test_scoring_rejects_unidentified_rows_mixed_into_v07(annotation_factory):
    rows = [
        annotation_factory(benchmark_version="0.7", benchmark_track="core"),
        annotation_factory(scenario_id="unknown-version"),
    ]
    with pytest.raises(ValidationError, match="provenance|mixed"):
        score_annotations(rows)


def test_scored_v07_result_retains_track_and_legacy_results_stay_unchanged(annotation_factory):
    result = score_annotations(
        [annotation_factory(benchmark_version="0.7", benchmark_track="core")]
    )[0].to_dict()
    assert result["benchmark_version"] == "0.7"
    assert result["benchmark_track"] == "core"
    legacy = score_annotations([annotation_factory()])[0].to_dict()
    assert "benchmark_version" not in legacy and "benchmark_track" not in legacy


@pytest.mark.parametrize("track", ["core", "agentic"])
def test_generated_v07_artifacts_carry_the_source_track(tmp_path, scenario_factory, track):
    fields = {
        "benchmark_version": "0.7",
        "benchmark_track": track,
        "scenario_id": f"v07-provenance-{track}",
    }
    if track == "agentic":
        fields.update(
            category="trajectory_recovery_and_correction",
            locale="en-US",
            protocol_mode="control",
            matched_pair_id="provenance-pair",
        )
    scenario = scenario_factory(**fields)
    source = tmp_path / "scenario.jsonl"
    source.write_text(json.dumps(scenario) + "\n")
    transcript = tmp_path / "transcript.jsonl"
    annotations = tmp_path / "annotations.jsonl"
    report = tmp_path / "report.json"

    def response(content):
        return {"choices": [{"message": {"role": "assistant", "content": content}}]}

    run_scenarios(
        scenarios_path=source,
        target_base_url="https://target.test/v1",
        target_model="candidate",
        candidate_digest="sha256:" + "a" * 64,
        output_path=transcript,
        transport=lambda *_: response("A bounded response."),
    )
    draft_evaluate(
        scenarios_path=source,
        transcripts_path=transcript,
        judge_base_url="https://judge.test/v1",
        judge_model="judge",
        output_path=annotations,
        report_path=report,
        transport=lambda *_: response(
            json.dumps(
                {
                    "scores": {d: 4 for d in scenario["dimensions"]},
                    "critical_failures": [],
                    "rationale": "Synthetic test rating, not human review.",
                }
            )
        ),
    )
    artifacts = [
        json.loads(transcript.read_text()),
        json.loads(annotations.read_text()),
        json.loads(report.read_text()),
    ]
    for artifact in artifacts:
        assert artifact["benchmark_version"] == "0.7"
        assert artifact["benchmark_track"] == track
    assert artifacts[2]["language_results"]["en"]["benchmark_track"] == track
    assert artifacts[2]["provenance"]["benchmark_track"] == track
