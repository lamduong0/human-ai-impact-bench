from __future__ import annotations

import json
from copy import deepcopy

import pytest

from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.experiments import (
    plan_study,
    run_study,
    validate_study,
    validate_study_state,
)
from humanai_impact_bench.validation import ValidationError


def study_manifest():
    return {
        "study_version": "0.8",
        "study_id": "test-study",
        "dataset_root": "dataset",
        "selection_path": "selection.json",
        "fixtures_path": None,
        "system_prompt_path": None,
        "targets": [
            {
                "id": f"t{i}",
                "family": f"target-family-{i}",
                "base_url": "https://target.example/v1",
                "model": f"target-{i}",
                "candidate_digest": "sha256:" + str(i) * 64,
                "max_tokens": 32,
                "temperature": 0,
                "api_key_env": None,
            }
            for i in (1, 2)
        ],
        "judges": [
            {
                "id": f"j{i}",
                "family": f"judge-family-{i}",
                "base_url": "https://judge.example/v1",
                "model": f"judge-{i}",
                "max_tokens": 64,
                "temperature": 0,
                "api_key_env": None,
            }
            for i in (1, 2)
        ],
        "generation_replicates": 2,
        "rating_replicates": 2,
        "retry_attempts": 2,
        "budget": {"max_requests": 10000, "max_output_tokens": 1000000},
        "analysis_seed": 20261105,
        "bootstrap_resamples": 2000,
    }


def records(scenario_factory, n=64):
    return [
        scenario_factory(
            benchmark_version="0.8",
            benchmark_track="core",
            scenario_id=f"v08-test-{i}",
            follow_up_prompts=["Please clarify.", "Help me take a small next step."],
            tags=[f"concept-family-test-{i}", f"context-test-{i}"],
        )
        for i in range(n)
    ]


def write_inputs(tmp_path, scenario_factory):
    rows = records(scenario_factory, 2)
    directory = tmp_path / "dataset" / "core" / "en"
    directory.mkdir(parents=True)
    (directory / "dependency_boundaries.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows)
    )
    selection = {
        "benchmark_version": "0.8",
        "records": [
            {
                "scenario_id": r["scenario_id"],
                "track": "core",
                "category": r["category"],
                "family_id": f"test-{i}",
                "context_id": f"test-{i}",
                "split": "calibration" if i == 0 else "public_evaluation",
                "scenario_digest": record_digest(r),
            }
            for i, r in enumerate(rows)
        ],
    }
    (tmp_path / "selection.json").write_text(json.dumps(selection))
    split_index = {
        "benchmark_version": "0.8",
        "assignments": {
            f"core|dependency_boundaries|test-{i}": entry["split"]
            for i, entry in enumerate(selection["records"])
        },
    }
    (tmp_path / "dataset/split-index.json").write_text(json.dumps(split_index))
    manifest = study_manifest()
    manifest["targets"] = manifest["targets"][:1]
    manifest["judges"] = manifest["judges"][:1]
    manifest["generation_replicates"] = 1
    manifest["rating_replicates"] = 1
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, rows


def test_plan_counts_full_matrix_and_retry_caps(scenario_factory):
    rows = records(scenario_factory)
    fixtures = [
        {"fixture_id": f"f-{i}", "scenario_id": rows[i % 32]["scenario_id"]} for i in range(192)
    ]
    result = plan_study(study_manifest(), rows, fixtures)
    assert result["generation_requests"] == 768
    assert result["rating_requests"] == 1024
    assert result["fixture_rating_requests"] == 768
    assert result["worst_case_requests"] == (768 + 1024 + 768) * 2
    assert len({t["task_id"] for t in result["tasks"]}) == len(result["tasks"])


def test_plan_rejects_budget_before_any_execution(scenario_factory):
    manifest = study_manifest()
    manifest["budget"]["max_requests"] = 1
    with pytest.raises(ValidationError, match="budget"):
        plan_study(manifest, records(scenario_factory), [])


@pytest.mark.parametrize(
    "change",
    [
        {"generation_replicates": True},
        {"retry_attempts": 0},
        {"rating_replicates": -1},
        {"analysis_seed": True},
        {"bootstrap_resamples": 1},
    ],
)
def test_manifest_rejects_invalid_counts(change):
    manifest = study_manifest()
    manifest.update(change)
    with pytest.raises(ValidationError):
        validate_study(manifest)


def fake_transport(url, payload, headers, timeout):
    if "judge" in payload["model"]:
        material = json.loads(payload["messages"][-1]["content"])
        judgment = {
            "scores": {d: 4 for d in material["scenario"]["dimensions"]},
            "critical_failures": [],
            "rationale": "Bounded, useful assistance.",
        }
        content = json.dumps(judgment)
    else:
        content = "I can help you think through this while keeping the choice yours."
    assert payload["max_tokens"] > 0
    return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def test_dry_run_never_calls_provider(tmp_path, scenario_factory):
    manifest_path, _ = write_inputs(tmp_path, scenario_factory)
    result = run_study(manifest_path=manifest_path, output_root=tmp_path / "run")
    assert result["execution_status"] == "not_run"
    assert not (tmp_path / "run").exists()


def test_complete_run_is_verifiable_and_resume_sends_nothing(tmp_path, scenario_factory):
    manifest_path, _ = write_inputs(tmp_path, scenario_factory)
    root = tmp_path / "run"
    result = run_study(
        manifest_path=manifest_path, output_root=root, dry_run=False, transport=fake_transport
    )
    assert result["execution_status"] == "complete"
    verified = validate_study_state(root / "study.json", root)
    assert len(verified["rows"]) == 2
    assert {r["split"] for r in verified["rows"]} == {"calibration", "public_evaluation"}

    def forbidden(*args):
        raise AssertionError("A completed run must not issue another request")

    resumed = run_study(
        manifest_path=manifest_path, output_root=root, dry_run=False, transport=forbidden
    )
    assert resumed["execution_status"] == "complete"


def test_timeout_preserves_partial_ledger_and_counts_attempts(tmp_path, scenario_factory):
    manifest_path, _ = write_inputs(tmp_path, scenario_factory)

    def failed(*args):
        raise RuntimeError("synthetic timeout")

    result = run_study(
        manifest_path=manifest_path, output_root=tmp_path / "run", dry_run=False, transport=failed
    )
    assert result["execution_status"] == "partial"
    state = validate_study_state(tmp_path / "run/study.json", tmp_path / "run")
    generations = [t for t in state["tasks"] if t["kind"] == "generation"]
    assert all(len(t["attempts"]) == 2 for t in generations)
    assert state["rows"] == []


def test_forged_annotation_rehash_cannot_replace_raw_judge_result(tmp_path, scenario_factory):
    from hashlib import sha256

    manifest_path, _ = write_inputs(tmp_path, scenario_factory)
    root = tmp_path / "run"
    run_study(
        manifest_path=manifest_path, output_root=root, dry_run=False, transport=fake_transport
    )
    state_path = root / "study-state.json"
    state = json.loads(state_path.read_text())
    task = next(t for t in state["tasks"] if t["kind"] == "rating")
    artifact = task["artifacts"]["annotation"]
    path = root / artifact["path"]
    annotation = json.loads(path.read_text().strip())
    annotation["scores"] = dict.fromkeys(annotation["scores"], 1)
    path.write_text(json.dumps(annotation) + "\n")
    artifact["sha256"] = sha256(path.read_bytes()).hexdigest()
    state_path.write_text(json.dumps(state))
    with pytest.raises(ValidationError, match="judge|annotation|raw"):
        validate_study_state(root / "study.json", root)


def test_changed_manifest_cannot_resume_completed_run(tmp_path, scenario_factory):
    manifest_path, _ = write_inputs(tmp_path, scenario_factory)
    root = tmp_path / "run"
    run_study(
        manifest_path=manifest_path, output_root=root, dry_run=False, transport=fake_transport
    )
    changed = deepcopy(json.loads(manifest_path.read_text()))
    changed["targets"][0]["model"] = "different-model"
    manifest_path.write_text(json.dumps(changed))
    with pytest.raises(ValidationError, match="different|match|resume"):
        run_study(
            manifest_path=manifest_path, output_root=root, dry_run=False, transport=fake_transport
        )


@pytest.mark.parametrize("tamper", ["extra_sampling", "system_digest", "annotation_scope"])
def test_rehashed_provenance_tampering_is_rejected(tmp_path, scenario_factory, tamper):
    from hashlib import sha256

    manifest_path, _ = write_inputs(tmp_path, scenario_factory)
    root = tmp_path / "run"
    run_study(
        manifest_path=manifest_path, output_root=root, dry_run=False, transport=fake_transport
    )
    state_path = root / "study-state.json"
    state = json.loads(state_path.read_text())
    generation = next(t for t in state["tasks"] if t["kind"] == "generation")
    if tamper == "extra_sampling":
        ref = generation["attempts"][0]["requests"][0]["request"]
        changed = json.loads((root / ref["path"]).read_text())
        changed["payload"]["top_p"] = 0.1
    elif tamper == "system_digest":
        ref = generation["artifacts"]["transcript"]
        changed = json.loads((root / ref["path"]).read_text())
        changed["system_prompt_digest"] = "a" * 64
    else:
        rating = next(t for t in state["tasks"] if t["kind"] == "rating")
        ref = rating["artifacts"]["annotation"]
        changed = json.loads((root / ref["path"]).read_text())
        changed["benchmark_version"] = "0.7"
    path = root / ref["path"]
    old_hash = ref["sha256"]
    path.write_text(json.dumps(changed) + "\n")
    new_hash = sha256(path.read_bytes()).hexdigest()

    def replace_refs(value):
        if isinstance(value, dict):
            if value.get("path") == ref["path"] and value.get("sha256") == old_hash:
                value["sha256"] = new_hash
            for child in value.values():
                replace_refs(child)
        elif isinstance(value, list):
            for child in value:
                replace_refs(child)

    replace_refs(state)
    state_path.write_text(json.dumps(state))
    with pytest.raises(ValidationError):
        validate_study_state(root / "study.json", root)


@pytest.mark.parametrize("problem", ["missing", "empty", "relabeled"])
def test_study_requires_inherited_split_metadata(tmp_path, scenario_factory, problem):
    manifest_path, _ = write_inputs(tmp_path, scenario_factory)
    splits = tmp_path / "dataset/split-index.json"
    if problem == "missing":
        splits.unlink()
    elif problem == "empty":
        splits.write_text(json.dumps({"assignments": {}}))
    else:
        selection_path = tmp_path / "selection.json"
        selection = json.loads(selection_path.read_text())
        selection["records"][0]["split"] = "public_evaluation"
        selection_path.write_text(json.dumps(selection))
    with pytest.raises(ValidationError):
        run_study(manifest_path=manifest_path, output_root=tmp_path / "out")


def test_changed_judge_instrument_cannot_resume_partial_run(
    tmp_path, scenario_factory, monkeypatch
):
    from humanai_impact_bench import deployment

    manifest_path, _ = write_inputs(tmp_path, scenario_factory)
    root = tmp_path / "run"

    def interrupted(url, payload, headers, timeout):
        if "judge" in payload["model"]:
            raise KeyboardInterrupt()
        return fake_transport(url, payload, headers, timeout)

    with pytest.raises(KeyboardInterrupt):
        run_study(
            manifest_path=manifest_path, output_root=root, dry_run=False, transport=interrupted
        )
    monkeypatch.setattr(deployment, "_JUDGE_SYSTEM_PROMPT", "Changed scoring instructions.")
    with pytest.raises(ValidationError, match="instrument|input|prompt"):
        run_study(
            manifest_path=manifest_path, output_root=root, dry_run=False, transport=fake_transport
        )


def test_failed_request_is_still_bound_to_planned_prompt(tmp_path, scenario_factory):
    from hashlib import sha256

    manifest_path, _ = write_inputs(tmp_path, scenario_factory)
    root = tmp_path / "run"

    def failed(*args):
        raise RuntimeError("synthetic provider error")

    run_study(manifest_path=manifest_path, output_root=root, dry_run=False, transport=failed)
    state_path = root / "study-state.json"
    state = json.loads(state_path.read_text())
    task = next(t for t in state["tasks"] if t["kind"] == "generation")
    ref = task["attempts"][0]["requests"][0]["request"]
    request_path = root / ref["path"]
    request = json.loads(request_path.read_text())
    request["payload"]["messages"] = [{"role": "user", "content": "unrelated request"}]
    request_path.write_text(json.dumps(request))
    ref["sha256"] = sha256(request_path.read_bytes()).hexdigest()
    state_path.write_text(json.dumps(state))
    with pytest.raises(ValidationError, match="prompt|input|source"):
        validate_study_state(root / "study.json", root)
