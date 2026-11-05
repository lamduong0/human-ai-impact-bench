from __future__ import annotations

import json
from copy import deepcopy

import pytest

from humanai_impact_bench import quality
from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.validation import ValidationError


def _record(factory, identity="v08-quality-001", **overrides):
    return factory(
        benchmark_version="0.8",
        benchmark_track="core",
        scenario_id=identity,
        tags=["concept-family-quality", "context-quality-one"],
        **overrides,
    )


def _metadata(records):
    return (
        {
            "entries": {
                r["scenario_id"]: {
                    "source_digest": "a" * 64,
                    "scenario_digest": record_digest(r),
                }
                for r in records
            }
        },
        {
            "assignments": {
                f"{r['benchmark_track']}|{r['category']}|quality": "calibration" for r in records
            }
        },
    )


def test_rejects_fabricated_quote(scenario_factory):
    scenario = _record(scenario_factory)
    assessment = {
        "dimension": "visible_grounding",
        "outcome": "flagged",
        "explanation": "The prompt contains an unsupported claim.",
        "evidence": [{"field": "initial_prompt", "quote": "not present"}],
    }
    with pytest.raises(ValidationError, match="quote"):
        quality.validate_assessment(assessment, scenario)


def test_context_cannot_masquerade_as_visible_input(scenario_factory):
    scenario = _record(scenario_factory)
    assessment = {
        "dimension": "visible_grounding",
        "outcome": "no_flag",
        "explanation": "The candidate sees this fact.",
        "evidence": [{"field": "initial_prompt", "quote": scenario["context"]}],
    }
    with pytest.raises(ValidationError, match="quote"):
        quality.validate_assessment(assessment, scenario)


def test_assessment_requires_index_for_list_fields(scenario_factory):
    scenario = _record(scenario_factory)
    assessment = {
        "dimension": "substantive_escalation",
        "outcome": "no_flag",
        "explanation": "A follow-up adds a demand.",
        "evidence": [{"field": "follow_up_prompts", "quote": "Promise"}],
    }
    with pytest.raises(ValidationError, match="index"):
        quality.validate_assessment(assessment, scenario)
    assessment["evidence"][0]["index"] = 0
    quality.validate_assessment(assessment, scenario)


def test_missing_record_is_not_clean(scenario_factory):
    first = _record(scenario_factory)
    second = _record(scenario_factory, "v08-quality-002")
    lineage, splits = _metadata([first, second])
    result = quality.audit_structure([first], lineage, splits)
    assert not result["valid"]
    assert any(f["kind"] == "missing_record" for f in result["findings"])


def test_stale_destination_digest_is_error(scenario_factory):
    record = _record(scenario_factory)
    lineage, splits = _metadata([record])
    record["initial_prompt"] = "A changed question."
    assert not quality.audit_structure([record], lineage, splits)["valid"]


def test_exact_control_stress_pair_is_not_duplicate(scenario_factory):
    control = _record(
        scenario_factory,
        "v08-quality-control",
        category="cross_session_memory_governance",
        locale="en-US",
        protocol_mode="control",
        matched_pair_id="v08-quality-pair",
    )
    control["benchmark_track"] = "agentic"
    stress = deepcopy(control)
    stress.update(
        scenario_id="v08-quality-stress",
        protocol_mode="prefill_stress",
        prefill_messages=[
            {"role": "user", "content": "Prior request."},
            {"role": "assistant", "content": "Prior reply."},
        ],
    )
    lineage, splits = _metadata([control, stress])
    result = quality.audit_structure([control, stress], lineage, splits)
    assert result["valid"]
    assert not any(f["kind"] == "duplicate_prompt" for f in result["findings"])
    stress["expected_behaviors"] = ["A different criterion"]
    lineage, splits = _metadata([control, stress])
    assert not quality.audit_structure([control, stress], lineage, splits)["valid"]


def _audit_source(tmp_path, scenario_factory):
    root = tmp_path / "v0.8"
    source = root / "core" / "en"
    source.mkdir(parents=True)
    record = _record(scenario_factory)
    (source / "dependency_boundaries.jsonl").write_text(json.dumps(record) + "\n")
    lineage, splits = _metadata([record])
    lineage["entries"][record["scenario_id"]].update(
        source_path="../v0.7/core/en/dependency_boundaries.jsonl",
        source_scenario_id="v07-quality-001",
    )
    old = deepcopy(record)
    old.update(benchmark_version="0.7", scenario_id="v07-quality-001")
    old_path = tmp_path / "v0.7/core/en/dependency_boundaries.jsonl"
    old_path.parent.mkdir(parents=True)
    old_path.write_text(json.dumps(old) + "\n")
    lineage["entries"][record["scenario_id"]]["source_digest"] = record_digest(old)
    (root / "lineage-index.json").write_text(json.dumps(lineage))
    (root / "split-index.json").write_text(json.dumps(splits))
    config = tmp_path / "audit-config.json"
    config.write_text(
        json.dumps(
            {
                "dataset_root": "v0.8",
                "model": "fixture-auditor",
                "base_url": "https://example.invalid/v1",
                "max_attempts": 2,
                "max_requests": 2,
                "max_output_tokens": 2000,
                "max_total_tokens": 100000,
                "temperature": 0,
                "timeout": 1,
            }
        )
    )
    return source, config, record


def test_offline_semantic_state_is_not_run(tmp_path, scenario_factory, monkeypatch):
    source, config, _ = _audit_source(tmp_path, scenario_factory)
    monkeypatch.setattr(quality, "_post_json", lambda *a: pytest.fail("offline network call"))
    report = quality.audit_scenarios(
        scenarios_path=source, config_path=config, output_path=tmp_path / "audit.json"
    )
    assert report["structural"]["valid"]
    assert report["semantic"]["status"] == "not_run"
    assert report["semantic"]["outcome_counts"] == {"not_run": 6}


def test_semantic_retry_error_is_counted(tmp_path, scenario_factory, monkeypatch):
    source, config, _ = _audit_source(tmp_path, scenario_factory)
    calls = []

    def invalid(url, payload, headers, timeout):
        calls.append(payload)
        return {"choices": [{"message": {"content": "not json"}}]}

    monkeypatch.setattr(quality, "_post_json", invalid)
    report = quality.audit_scenarios(
        scenarios_path=source,
        config_path=config,
        output_path=tmp_path / "audit.json",
        automated=True,
    )
    assert len(calls) == 2
    assert all(p["max_tokens"] == 2000 for p in calls)
    assert report["semantic"]["outcome_counts"] == {"error": 6}
    assert report["semantic"]["status"] == "partial"
    assert report["semantic"]["attempt_count"] == 2


def test_semantic_valid_results_bind_provenance(tmp_path, scenario_factory, monkeypatch):
    source, config, record = _audit_source(tmp_path, scenario_factory)
    assessments = [
        {
            "dimension": dim,
            "outcome": "no_flag",
            "explanation": "Test assessment.",
            "evidence": [{"field": "initial_prompt", "quote": record["initial_prompt"]}],
        }
        for dim in quality.ASSESSMENT_DIMENSIONS
    ]
    raw = json.dumps({"assessments": assessments})
    monkeypatch.setattr(
        quality, "_post_json", lambda *a: {"choices": [{"message": {"content": raw}}]}
    )
    report = quality.audit_scenarios(
        scenarios_path=source,
        config_path=config,
        output_path=tmp_path / "audit.json",
        automated=True,
    )
    assert report["semantic"]["outcome_counts"] == {"no_flag": 6}
    assert report["semantic"]["status"] == "complete"
    assert report["evidence_stage"] == "PREVIEW"
    assert report["semantic"]["records"][0]["scenario_digest"] == record_digest(record)
    assert report["semantic"]["records"][0]["attempts"][0]["raw_output_digest"]


def test_request_cap_prevents_any_call(tmp_path, scenario_factory, monkeypatch):
    source, config, _ = _audit_source(tmp_path, scenario_factory)
    settings = json.loads(config.read_text())
    settings["max_requests"] = 1
    config.write_text(json.dumps(settings))
    monkeypatch.setattr(quality, "_post_json", lambda *a: pytest.fail("budget not enforced"))
    with pytest.raises(ValidationError, match="budget|requests"):
        quality.audit_scenarios(
            scenarios_path=source,
            config_path=config,
            output_path=tmp_path / "audit.json",
            automated=True,
        )


def test_source_hash_is_verified(tmp_path, scenario_factory):
    source, config, _ = _audit_source(tmp_path, scenario_factory)
    path = tmp_path / "v0.7/core/en/dependency_boundaries.jsonl"
    old = json.loads(path.read_text())
    old["title"] = "Modified historical source"
    path.write_text(json.dumps(old) + "\n")
    result = quality.audit_scenarios(
        scenarios_path=source, config_path=config, output_path=tmp_path / "audit.json"
    )
    assert not result["structural"]["valid"]
    assert any(f["kind"] == "source_digest_mismatch" for f in result["structural"]["findings"])


def test_semantic_flags_have_unresolved_findings(tmp_path, scenario_factory, monkeypatch):
    source, config, record = _audit_source(tmp_path, scenario_factory)
    assessments = [
        {
            "dimension": dim,
            "outcome": "flagged",
            "explanation": "Fixture finding.",
            "evidence": [{"field": "initial_prompt", "quote": record["initial_prompt"]}],
        }
        for dim in quality.ASSESSMENT_DIMENSIONS
    ]
    monkeypatch.setattr(
        quality,
        "_post_json",
        lambda *a: {
            "choices": [{"message": {"content": json.dumps({"assessments": assessments})}}]
        },
    )
    result = quality.audit_scenarios(
        scenarios_path=source,
        config_path=config,
        output_path=tmp_path / "audit.json",
        automated=True,
    )
    assert len(result["semantic"]["findings"]) == 6
    assert {r["disposition"] for r in result["semantic"]["findings"]} == {"unresolved"}


def test_fixed_disposition_requires_actual_source_change():
    findings = [{"finding_id": "test"}]
    ledger = [
        {
            "finding_id": "test",
            "disposition": "fixed",
            "reason": "Corrected rubric",
            "origin": "automated",
            "old_digest": "a" * 64,
            "new_digest": "a" * 64,
            "reassessment_digest": "b" * 64,
        }
    ]
    with pytest.raises(ValidationError, match="change"):
        quality.validate_dispositions(ledger, findings)


def test_audit_report_satisfies_published_schema(tmp_path, scenario_factory):
    from pathlib import Path

    from jsonschema import Draft202012Validator

    source, config, _ = _audit_source(tmp_path, scenario_factory)
    result = quality.audit_scenarios(
        scenarios_path=source, config_path=config, output_path=tmp_path / "audit.json"
    )
    schema = Path(__file__).resolve().parents[1] / "schemas/scenario-audit-v0.8.schema.json"
    Draft202012Validator(json.loads(schema.read_text())).validate(result)
