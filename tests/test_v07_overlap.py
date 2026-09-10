from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.audit_v07_overlap import build_report
from scripts.v07_artifacts import build_split_index


def save(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.fixture
def corpus(tmp_path, scenario_factory):
    root = tmp_path / "v0.7"
    for track, category in (
        ("core", "dependency_boundaries"),
        ("agentic", "cross_session_memory_governance"),
    ):
        for language in ("en", "vi"):
            records = []
            for i in range(25):
                seed = f"{track}-{language}-{i}"
                prose = [
                    hashlib.sha512(f"{seed}-{field}".encode()).hexdigest() for field in range(5)
                ]
                pair = f"v07-{track}-{i:02}-01-{language}"
                for mode in ("control", "prefill_stress") if track == "agentic" else (None,):
                    sid = f"v07-{track}-{i:02}-01" + (
                        f"-{language}-{mode.replace('_', '-')}" if mode else ""
                    )
                    tags = [
                        f"concept-family-{track}-{i:02}",
                        f"context-{track}-{i:02}-01",
                        "authoring-model-assisted",
                    ]
                    if language == "vi":
                        source = sid.replace("-vi-", "-en-")
                        tags += [
                            "derivation-adapted",
                            "source-version-v0-7",
                            "source-language-en",
                            f"source-scenario-{source}",
                            "requires-cultural-review",
                        ]
                    else:
                        tags += ["derivation-authored-new"]
                    record = scenario_factory(
                        benchmark_version="0.7",
                        benchmark_track=track,
                        scenario_id=sid,
                        category=category,
                        language=language,
                        risk_level="moderate",
                        context=prose[0],
                        initial_prompt=prose[1],
                        follow_up_prompts=[prose[2]],
                        expected_behaviors=[prose[3]],
                        failure_modes=[prose[4]],
                        tags=tags,
                    )
                    if mode:
                        record.update(
                            locale="vi-VN" if language == "vi" else "en-US",
                            protocol_mode=mode,
                            matched_pair_id=pair,
                        )
                        record["tags"] += [
                            f"protocol-{mode.replace('_', '-')}",
                            f"locale-{record['locale']}",
                        ]
                        if mode == "prefill_stress":
                            record["prefill_messages"] = [
                                {"role": "user", "content": "Synthetic prior fact " + prose[0]},
                                {
                                    "role": "assistant",
                                    "content": "Synthetic unsupported claim " + prose[1],
                                },
                            ]
                    records.append(record)
            save(root / track / language / f"{category}.jsonl", records)
    return root


def test_clean_fixture_and_intended_pairs_have_no_unresolved_overlap(corpus):
    result = build_report(corpus)
    assert result["valid"] is True
    assert result["scenario_count"] == 150
    assert result["unresolved_candidate_ids"] == []
    assert result["text_unit_count"] == 100


def test_direct_script_entrypoint_composes_helpers_outside_the_repo(corpus):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/audit_v07_overlap.py"),
            "--root",
            str(corpus),
            "--output",
            str(corpus / "overlap-audit.json"),
        ],
        cwd=corpus.parent,
        env={**os.environ, "PYTHONPATH": str(root / "src")},
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True


@pytest.mark.parametrize("kind", ["exact_prompt", "template_phrase", "lexical_similarity"])
def test_overlap_algorithms_find_actual_unrelated_candidates(corpus, kind):
    path = corpus / "core/en/dependency_boundaries.jsonl"
    rows = load(path)
    if kind == "exact_prompt":
        rows[1]["initial_prompt"] = rows[0]["initial_prompt"]
        rows[1]["follow_up_prompts"] = rows[0]["follow_up_prompts"]
    elif kind == "template_phrase":
        for row in rows[:3]:
            row["initial_prompt"] = (
                "These seven repeated words form a conspicuous template " + row["initial_prompt"]
            )
    else:
        rows[0]["initial_prompt"] = (
            "I want to compare the two available choices before making a decision tonight."
        )
        rows[1]["initial_prompt"] = (
            "I want to compare the three available choices before making a decision tomorrow."
        )
        rows[0]["follow_up_prompts"] = [
            "Consider the evidence and the remaining uncertainty carefully."
        ]
        rows[1]["follow_up_prompts"] = [
            "Consider the evidence and the remaining uncertainty closely."
        ]
    save(path, rows)
    report = build_report(corpus)
    assert report["valid"] is False
    assert any(
        c["kind"] == kind and c["candidate_id"] in report["unresolved_candidate_ids"]
        for c in report["candidates"]
    )


@pytest.mark.parametrize("defect", ["missing", "mismatched"])
def test_invalid_agentic_pairs_do_not_get_duplicate_exemption(corpus, defect):
    path = corpus / "agentic/en/cross_session_memory_governance.jsonl"
    rows = load(path)
    if defect == "missing":
        rows.pop(1)
    else:
        rows[1]["failure_modes"] = ["A different scoring contract."]
    save(path, rows)
    report = build_report(corpus)
    assert report["valid"] is False
    assert any("pair" in issue for issue in report["structural_issues"])


@pytest.mark.parametrize("kind", ["exact_component", "template_phrase"])
def test_synthetic_prefill_text_is_screened_separately_from_pair_common_text(corpus, kind):
    path = corpus / "agentic/en/cross_session_memory_governance.jsonl"
    rows = load(path)
    for index in (1, 3, 5):
        phrase = "This repeated synthetic history supplies an unsafe prior rule"
        if kind == "template_phrase":
            phrase += " " + rows[index]["initial_prompt"]
        rows[index]["prefill_messages"][1]["content"] = phrase
    save(path, rows)
    report = build_report(corpus)
    candidates = [
        c
        for c in report["candidates"]
        if c["kind"] == kind and "prefill_assistant" in c["evidence"]
    ]
    assert report["valid"] is False
    assert candidates
    assert all(member.endswith("-prefill-stress") for c in candidates for member in c["members"])


def test_prefill_history_is_also_compared_with_public_legacy_prefills(corpus):
    current = load(corpus / "agentic/en/cross_session_memory_governance.jsonl")[1]
    legacy = deepcopy(current)
    legacy.pop("benchmark_track")
    legacy.update(
        benchmark_version="0.5",
        scenario_id="legacy-prefill",
        category="memory_consent_and_personalization",
        protocol_mode="prefill_recovery",
    )
    save(corpus.parent / "v0.5/memory_consent_and_personalization.jsonl", [legacy])
    report = build_report(corpus)
    assert report["valid"] is False
    assert any(
        c["kind"] == "exact_component"
        and "prefill_assistant" in c["evidence"]
        and "0.5/legacy/en/legacy-prefill" in c["members"]
        for c in report["candidates"]
    )


def test_existing_split_leak_is_detected_without_requiring_an_index(corpus):
    assert not (corpus / "configuration-index.json").exists()
    split = build_split_index(corpus)
    first = split["items"][0]
    first["split"] = "public_evaluation" if first["split"] == "calibration" else "calibration"
    (corpus / "split-index.json").write_text(json.dumps(split))
    report = build_report(corpus)
    assert report["valid"] is False
    assert any("split" in issue for issue in report["structural_issues"])


def test_shared_family_cannot_land_in_two_computed_splits(corpus):
    rows = deepcopy(load(corpus / "core/en/dependency_boundaries.jsonl"))
    for i, row in enumerate(rows):
        row["category"] = "grief_and_loss"
        row["scenario_id"] = f"v07-other-{i}"
        family = "core-00" if i == 24 else f"aaa-{i:02}"
        row["tags"] = [f"concept-family-{family}", f"context-other-{i}", "derivation-authored-new"]
    save(corpus / "core/en/grief_and_loss.jsonl", rows)
    report = build_report(corpus)
    assert report["valid"] is False
    assert any("split leakage" in issue for issue in report["structural_issues"])


def test_quarantine_directory_is_never_read(corpus):
    pending = corpus.parent / "pending-safety-review/minor_safety.jsonl"
    pending.parent.mkdir()
    pending.write_text("not even valid JSON\n")
    report = build_report(corpus)
    assert report["valid"] is True
    assert report["historical_scenario_count"] == 0


def test_invalid_public_history_produces_failed_audit_not_partial_success(corpus):
    path = corpus.parent / "v0.6/en/broken.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("broken JSON\n")
    report = build_report(corpus)
    assert report["valid"] is False
    assert any("historical" in issue for issue in report["structural_issues"])


@pytest.mark.parametrize("invalid", ["null", "not JSON"])
def test_invalid_prior_resolution_artifact_cannot_yield_success(corpus, invalid):
    (corpus / "overlap-audit.json").write_text(invalid)
    report = build_report(corpus)
    assert report["valid"] is False
    assert any("resolution" in issue for issue in report["structural_issues"])


def test_quarantined_membership_cannot_enter_historical_comparison(corpus):
    record = deepcopy(load(corpus / "core/en/dependency_boundaries.jsonl")[0])
    record.pop("benchmark_track")
    record.update(benchmark_version="0.6", scenario_id="pending-minor", category="minor_safety")
    save(corpus.parent / "v0.6/en/escaped.jsonl", [record])
    report = build_report(corpus)
    assert report["valid"] is False
    assert any("quarantin" in issue for issue in report["structural_issues"])


def test_cross_version_overlap_and_declared_source_dispositions(corpus):
    path = corpus / "core/en/dependency_boundaries.jsonl"
    rows = load(path)
    legacy = deepcopy(rows[0])
    legacy.pop("benchmark_track")
    legacy.update(benchmark_version="0.6", scenario_id="legacy-source", tags=[])
    save(corpus.parent / "v0.6/en/dependency_boundaries.jsonl", [legacy])
    report = build_report(corpus)
    assert report["valid"] is False
    assert any("0.6/legacy/en/legacy-source" in c["members"] for c in report["candidates"])
    rows[0]["tags"] = [t for t in rows[0]["tags"] if not t.startswith("derivation-")] + [
        "derivation-adapted",
        "source-version-v0-6",
        "source-scenario-legacy-source",
    ]
    save(path, rows)
    report = build_report(corpus)
    assert report["valid"] is True
    assert all(r["decision"] == "source_preserving" for r in report["resolutions"])


def test_unresolved_disposition_is_not_filled_by_null_or_unrelated_approval(corpus):
    path = corpus / "core/en/dependency_boundaries.jsonl"
    rows = load(path)
    rows[1]["initial_prompt"] = rows[0]["initial_prompt"]
    save(path, rows)
    report = build_report(corpus)
    report["resolutions"] = [None]
    (corpus / "overlap-audit.json").write_text(json.dumps(report))
    rebuilt = build_report(corpus)
    assert rebuilt["valid"] is False
    assert rebuilt["unresolved_candidate_ids"]
    assert any("resolution" in issue for issue in rebuilt["structural_issues"])


def test_historical_digest_change_invalidates_reused_manual_dispositions(corpus):
    path = corpus / "core/en/dependency_boundaries.jsonl"
    rows = load(path)
    legacy = deepcopy(rows[0])
    legacy.pop("benchmark_track")
    legacy.update(benchmark_version="0.6", scenario_id="legacy-unrelated", tags=[])
    history_path = corpus.parent / "v0.6/en/dependency_boundaries.jsonl"
    save(history_path, [legacy])
    report = build_report(corpus)
    report["resolutions"] += [
        {
            "candidate_id": cid,
            "decision": "accepted_distinct",
            "rationale": "Synthetic fixture decision, explicitly scoped to this exact candidate.",
        }
        for cid in report["unresolved_candidate_ids"]
    ]
    (corpus / "overlap-audit.json").write_text(json.dumps(report))
    assert build_report(corpus)["valid"] is True
    legacy["context"] += " A changed historical source."
    save(history_path, [legacy])
    updated = build_report(corpus)
    assert updated["historical_sha256"] != report["historical_sha256"]
    assert updated["valid"] is False
    assert updated["stale_resolution_count"] > 0


def test_changed_member_text_invalidates_manual_decision_even_when_candidate_id_is_unchanged(
    corpus,
):
    path = corpus / "core/en/dependency_boundaries.jsonl"
    rows = load(path)
    rows[1]["initial_prompt"] = rows[0]["initial_prompt"]
    save(path, rows)
    report = build_report(corpus)
    unresolved = set(report["unresolved_candidate_ids"])
    assert unresolved
    report["resolutions"] += [
        {
            "candidate_id": cid,
            "decision": "accepted_distinct",
            "rationale": "Synthetic fixture decision for the inspected original prompt and rubric.",
        }
        for cid in sorted(unresolved)
    ]
    (corpus / "overlap-audit.json").write_text(json.dumps(report))
    assert build_report(corpus)["valid"] is True
    # The repeated initial prompt and lexical ratios stay identical; this unique
    # rubric item is outside the candidate's triggering evidence but changes
    # what a reviewer assessed about the member's meaning.
    rows[0]["failure_modes"] = ["A newly changed unique rubric sentence."]
    save(path, rows)
    rebuilt = build_report(corpus)
    assert unresolved <= {c["candidate_id"] for c in rebuilt["candidates"]}
    assert unresolved <= set(rebuilt["unresolved_candidate_ids"])
    assert rebuilt["stale_resolution_count"] > 0
    assert rebuilt["valid"] is False
