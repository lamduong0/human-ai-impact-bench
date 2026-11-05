from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from humanai_impact_bench.deployment import draft_evaluate, evaluate_gate, run_scenarios
from humanai_impact_bench.scoring import score_annotations
from humanai_impact_bench.validation import ValidationError, validate_scenario

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("track", ["core", "agentic"])
def test_v08_english_contract_and_schema(scenario_factory, track):
    record = scenario_factory(benchmark_version="0.8", benchmark_track=track)
    if track == "agentic":
        record.update(
            category="trajectory_recovery_and_correction",
            locale="en-US",
            protocol_mode="control",
            matched_pair_id="v08-test-pair",
        )
    validate_scenario(record)
    schema = json.loads((ROOT / "schemas/scenario.schema.json").read_text())
    Draft202012Validator(schema).validate(record)
    record["language"] = "vi"
    with pytest.raises(ValidationError, match="English|language"):
        validate_scenario(record)
    assert not Draft202012Validator(schema).is_valid(record)


def test_v08_requires_scope_even_without_explicit_version(annotation_factory):
    annotation = annotation_factory(scenario_id="v08-case")
    with pytest.raises(ValidationError, match="provenance"):
        score_annotations([annotation])


def test_v08_scores_keep_scope_and_reject_mixing(annotation_factory):
    item = annotation_factory(benchmark_version="0.8", benchmark_track="core")
    assert score_annotations([item])[0].benchmark_version == "0.8"
    with pytest.raises(ValidationError, match="scope|mixed|mix"):
        score_annotations(
            [
                item,
                annotation_factory(benchmark_version="0.7", benchmark_track="core", model="other"),
            ]
        )


def test_v08_agentic_candidate_only_judgment_and_hold(tmp_path, scenario_factory):
    item = scenario_factory(
        benchmark_version="0.8",
        benchmark_track="agentic",
        scenario_id="v08-test-case",
        category="trajectory_recovery_and_correction",
        locale="en-US",
        protocol_mode="prefill_stress",
        matched_pair_id="v08-test-pair",
        prefill_messages=[
            {"role": "user", "content": "Synthetic earlier request."},
            {"role": "assistant", "content": "Synthetic unsafe claim."},
        ],
    )
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps(item) + "\n")
    transcripts = tmp_path / "transcripts.jsonl"
    report = tmp_path / "report.json"
    policy = tmp_path / "policy.json"
    p = json.loads((ROOT / "configs/draft-gate.json").read_text())
    p["requirements"].update(
        minimum_scenario_records=1,
        minimum_unique_scenarios=1,
        required_languages=["en"],
        minimum_annotations_per_dimension=1,
    )
    p["thresholds"]["dimension_scores"] = {d: 0 for d in item["dimensions"]}
    policy.write_text(json.dumps(p))

    def response(content):
        return {"choices": [{"message": {"content": content}}]}

    run_scenarios(
        scenarios_path=source,
        target_base_url="https://target.test/v1",
        target_model="candidate",
        candidate_digest="sha256:" + "a" * 64,
        output_path=transcripts,
        transport=lambda *_: response("A bounded answer."),
    )
    prompts = []

    def judge(_url, payload, _headers, _timeout):
        assert payload["max_tokens"] == 256
        material = json.loads(payload["messages"][1]["content"])
        prompts.append(material)
        return response(
            json.dumps(
                {
                    "scores": {d: 5 for d in item["dimensions"]},
                    "critical_failures": [],
                    "rationale": "Synthetic test.",
                }
            )
        )

    draft_evaluate(
        scenarios_path=source,
        transcripts_path=transcripts,
        judge_base_url="https://judge.test/v1",
        judge_model="judge",
        output_path=tmp_path / "annotations.jsonl",
        report_path=report,
        policy_path=policy,
        transport=judge,
        judge_max_tokens=256,
    )
    assert len(prompts[0]["candidate_messages"]) == 2
    assert all(m["content"] == "A bounded answer." for m in prompts[0]["candidate_messages"])
    assert json.loads(report.read_text())["benchmark_version"] == "0.8"
    gate = evaluate_gate(report_path=report, policy_path=policy)
    assert gate["deployment_action"] == "HOLD"
    assert gate["gate_decision"] == "REVIEW_REQUIRED"

    forged = json.loads(transcripts.read_text())
    forged["benchmark_version"] = "0.7"
    transcripts.write_text(json.dumps(forged) + "\n")
    with pytest.raises(ValidationError, match="benchmark_version"):
        draft_evaluate(
            scenarios_path=source,
            transcripts_path=transcripts,
            judge_base_url="https://judge.test/v1",
            judge_model="judge",
            output_path=tmp_path / "forged-annotations.jsonl",
            report_path=tmp_path / "forged.json",
            transport=judge,
            judge_max_tokens=256,
        )
