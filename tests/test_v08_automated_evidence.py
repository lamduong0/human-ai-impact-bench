from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

import humanai_impact_bench.automated_evidence as evidence
from humanai_impact_bench.robustness import build_study_report
from humanai_impact_bench.validation import ValidationError


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


def reference(root, name):
    return {"path": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    manifest = {"study_version": "0.8", "study_id": "test-only"}
    validated = {
        "manifest": manifest,
        "tasks": [],
        "scenarios": [],
        "fixtures": [],
        "execution_status": "not_run",
        "rows": [],
    }
    write_json(tmp_path / "study.json", manifest)
    write_json(tmp_path / "study-state.json", {"tasks": []})
    write_json(tmp_path / "report.json", build_study_report(validated))
    document = {
        "bundle_version": "0.8",
        "manifest": reference(tmp_path, "study.json"),
        "state": reference(tmp_path, "study-state.json"),
        "report": reference(tmp_path, "report.json"),
        "artifacts": [],
    }
    write_json(tmp_path / "bundle.json", document)
    monkeypatch.setattr(evidence, "_validate_state", lambda manifest, root: deepcopy(validated))
    return tmp_path, document, validated


def test_not_run_bundle_verifies_integrity_without_promoting_evidence(bundle):
    root, _, _ = bundle
    result = evidence.verify_automated_evidence(root / "bundle.json")
    assert result["artifact_integrity"] == "verified"
    assert result["execution_status"] == "not_run"
    assert result["evidence_stage"] == "PREVIEW"
    assert result["human_review"] == "not_performed"
    assert result["deployment_action"] == "HOLD"


def test_modified_file_rejects_stale_hash(bundle):
    root, _, _ = bundle
    (root / "report.json").write_text("{}")
    with pytest.raises(ValidationError, match="digest"):
        evidence.verify_automated_evidence(root / "bundle.json")


def test_rehashed_wrong_report_fails_recomputation(bundle):
    root, document, _ = bundle
    report = json.loads((root / "report.json").read_text())
    report["coverage"]["completed_tasks"] = 100
    write_json(root / "report.json", report)
    document["report"] = reference(root, "report.json")
    write_json(root / "bundle.json", document)
    with pytest.raises(ValidationError, match="recomputed"):
        evidence.verify_automated_evidence(root / "bundle.json")


@pytest.mark.parametrize("bad_path", ["../outside.json", "/tmp/absolute.json", "foo/../study.json"])
def test_invalid_paths_are_rejected_before_open(bundle, bad_path):
    root, document, _ = bundle
    document["manifest"]["path"] = bad_path
    write_json(root / "bundle.json", document)
    with pytest.raises(ValidationError, match="path|inside"):
        evidence.verify_automated_evidence(root / "bundle.json")


def test_escaping_symlink_is_rejected(bundle):
    root, document, _ = bundle
    outside = root.parent / "outside.json"
    outside.write_text("{}")
    (root / "escape.json").symlink_to(outside)
    document["artifacts"] = [{"path": "escape.json", "sha256": hashlib.sha256(b"{}").hexdigest()}]
    write_json(root / "bundle.json", document)
    with pytest.raises(ValidationError, match="inside"):
        evidence.verify_automated_evidence(root / "bundle.json")


def test_duplicate_artifact_and_missing_file_are_rejected(bundle):
    root, document, _ = bundle
    document["artifacts"] = [document["manifest"]]
    write_json(root / "bundle.json", document)
    with pytest.raises(ValidationError, match="duplicate"):
        evidence.verify_automated_evidence(root / "bundle.json")
    document["artifacts"] = [{"path": "missing.json", "sha256": "a" * 64}]
    write_json(root / "bundle.json", document)
    with pytest.raises(ValidationError, match="missing|read|file"):
        evidence.verify_automated_evidence(root / "bundle.json")


def test_state_reference_cannot_differ_from_validated_state(bundle):
    root, document, _ = bundle
    write_json(root / "different-state.json", {"tasks": []})
    document["state"] = reference(root, "different-state.json")
    write_json(root / "bundle.json", document)
    with pytest.raises(ValidationError, match="study-state"):
        evidence.verify_automated_evidence(root / "bundle.json")


def test_nested_request_must_be_in_inventory(bundle):
    root, document, _ = bundle
    write_json(root / "raw/request.json", {"model": "test"})
    write_json(
        root / "study-state.json",
        {
            "tasks": [
                {"attempts": [{"requests": [{"request": "raw/request.json", "response": None}]}]}
            ]
        },
    )
    document["state"] = reference(root, "study-state.json")
    write_json(root / "bundle.json", document)
    with pytest.raises(ValidationError, match="inventory"):
        evidence.verify_automated_evidence(root / "bundle.json")


def test_nonfinite_and_duplicate_json_members_rejected(bundle):
    root, _, _ = bundle
    (root / "bundle.json").write_text('{"bundle_version":"0.8","bundle_version":"0.8"}')
    with pytest.raises(ValidationError, match="duplicate"):
        evidence.verify_automated_evidence(root / "bundle.json")
    (root / "bundle.json").write_text('{"bundle_version":"0.8","extra":NaN}')
    with pytest.raises(ValidationError, match="finite"):
        evidence.verify_automated_evidence(root / "bundle.json")
    (root / "bundle.json").write_text('{"bundle_version":"0.8","extra":1e999}')
    with pytest.raises(ValidationError, match="finite"):
        evidence.verify_automated_evidence(root / "bundle.json")


def test_metric_type_mismatch_cannot_hide_behind_numeric_equality(bundle):
    root, document, _ = bundle
    report = json.loads((root / "report.json").read_text())
    report["coverage"]["completed_tasks"] = False
    write_json(root / "report.json", report)
    document["report"] = reference(root, "report.json")
    write_json(root / "bundle.json", document)
    with pytest.raises(ValidationError, match="recomputed"):
        evidence.verify_automated_evidence(root / "bundle.json")


def _run_small_study(tmp_path, scenario_factory, *, fail=False):
    from humanai_impact_bench.digests import record_digest
    from humanai_impact_bench.experiments import run_study
    from humanai_impact_bench.robustness import report_study

    scenario = scenario_factory(
        benchmark_version="0.8",
        benchmark_track="core",
        scenario_id="v08-integration",
        follow_up_prompts=["Please clarify.", "Help me take a small next step."],
        tags=["concept-family-integration", "context-integration"],
    )
    source = tmp_path / "dataset/core/en/dependency_boundaries.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(scenario) + "\n")
    selection = {
        "benchmark_version": "0.8",
        "records": [
            {
                "scenario_id": scenario["scenario_id"],
                "track": "core",
                "category": scenario["category"],
                "family_id": "integration",
                "context_id": "integration",
                "split": "public_evaluation",
                "scenario_digest": record_digest(scenario),
            }
        ],
    }
    write_json(tmp_path / "selection.json", selection)
    write_json(
        tmp_path / "dataset/split-index.json",
        {"assignments": {"core|dependency_boundaries|integration": "public_evaluation"}},
    )
    manifest = {
        "study_version": "0.8",
        "study_id": "integration-test",
        "dataset_root": "dataset",
        "selection_path": "selection.json",
        "fixtures_path": None,
        "system_prompt_path": None,
        "targets": [
            {
                "id": "t1",
                "family": "target-family",
                "base_url": "https://target.example/v1",
                "model": "target",
                "candidate_digest": "sha256:" + "a" * 64,
                "max_tokens": 32,
                "temperature": 0,
                "api_key_env": None,
            }
        ],
        "judges": [
            {
                "id": "j1",
                "family": "judge-family",
                "base_url": "https://judge.example/v1",
                "model": "judge",
                "max_tokens": 64,
                "temperature": 0,
                "api_key_env": None,
            }
        ],
        "generation_replicates": 1,
        "rating_replicates": 1,
        "retry_attempts": 2,
        "budget": {"max_requests": 100, "max_output_tokens": 10000},
        "analysis_seed": 20261105,
        "bootstrap_resamples": 2000,
    }
    write_json(tmp_path / "manifest.json", manifest)

    def transport(url, payload, headers, timeout):
        if fail:
            raise RuntimeError("synthetic transport error")
        if payload["model"] == "judge":
            material = json.loads(payload["messages"][-1]["content"])
            content = json.dumps(
                {
                    "scores": {d: 4 for d in material["scenario"]["dimensions"]},
                    "critical_failures": [],
                    "rationale": "Synthetic unit test.",
                }
            )
        else:
            content = "I can help you consider options while keeping the choice yours."
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}

    root = tmp_path / "run"
    run_study(
        manifest_path=tmp_path / "manifest.json",
        output_root=root,
        dry_run=False,
        transport=transport,
    )
    report_study(manifest_path=root / "study.json", run_root=root, output_path=root / "report.json")
    evidence.write_evidence_bundle(root, root / "report.json", root / "bundle.json")
    return root


@pytest.mark.parametrize("failed,expected", [(False, "complete"), (True, "partial")])
def test_full_local_study_bundle_verifies_actual_captured_artifacts(
    tmp_path, scenario_factory, failed, expected
):
    root = _run_small_study(tmp_path, scenario_factory, fail=failed)
    result = evidence.verify_automated_evidence(root / "bundle.json")
    assert result["execution_status"] == expected
    assert result["evidence_stage"] == "PREVIEW"
    assert result["comparison_complete"] is (not failed)


def test_rehashed_complete_report_tampering_is_rejected_end_to_end(tmp_path, scenario_factory):
    root = _run_small_study(tmp_path, scenario_factory)
    report = json.loads((root / "report.json").read_text())
    report["candidate_results"][0]["scores"]["overall_score"] = 99
    write_json(root / "report.json", report)
    evidence.write_evidence_bundle(root, root / "report.json", root / "bundle.json")
    with pytest.raises(ValidationError, match="recomputed"):
        evidence.verify_automated_evidence(root / "bundle.json")


def test_bundle_writer_rejects_external_report_and_escaping_symlink(bundle):
    root, _, _ = bundle
    with pytest.raises(ValidationError, match="inside"):
        evidence.write_evidence_bundle(root, root.parent / "outside.json", root / "bundle.json")
    (root / "escape").symlink_to(Path("/tmp"), target_is_directory=True)
    with pytest.raises(ValidationError, match="inside"):
        evidence.write_evidence_bundle(root, root / "report.json", root / "bundle.json")


def test_bundle_writer_rejects_nested_location_before_writing(bundle):
    root, _, _ = bundle
    output = root / "exports/bundle.json"
    with pytest.raises(ValidationError, match="study root"):
        evidence.write_evidence_bundle(root, root / "report.json", output)
    assert not output.exists()
    assert not output.parent.exists()
