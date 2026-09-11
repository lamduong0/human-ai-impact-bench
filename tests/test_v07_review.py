from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from humanai_impact_bench.review import (
    derive_review_status,
    scenario_digest,
    validate_v07_review_manifest,
)
from humanai_impact_bench.validation import ValidationError
from scripts.generate_v07_review_manifests import build_manifest, write_manifest
from scripts.validate_cultural_review import validate_review_manifest


@pytest.fixture
def v07_fixture_dir(tmp_path: Path, scenario_factory) -> Path:
    source_dir = tmp_path / "core" / "en"
    source_dir.mkdir(parents=True)
    scenarios = [
        scenario_factory(
            benchmark_version="0.7",
            benchmark_track="core",
            scenario_id="review-fixture-001",
            risk_level="low",
            tags=[
                "concept-family-review-001",
                "context-review-001",
                "derivation-authored-new",
            ],
        ),
        scenario_factory(
            benchmark_version="0.7",
            benchmark_track="core",
            scenario_id="review-fixture-002",
            risk_level="low",
            tags=[
                "concept-family-review-002",
                "context-review-002",
                "derivation-authored-new",
            ],
        ),
    ]
    (source_dir / "dependency_boundaries.jsonl").write_text(
        "".join(json.dumps(scenario) + "\n" for scenario in scenarios),
        encoding="utf-8",
    )
    return source_dir


def _review_event(scenario: dict, **overrides: str) -> dict[str, str]:
    event = {
        "review_type": "construct",
        "reviewer_id": "reviewer-001",
        "qualification": "documented domain qualification",
        "decision": "approved",
        "reviewed_at": "2026-09-07T00:00:00Z",
        "conflict_disclosure": "no author conflict",
        "reviewed_locale": "en-US",
        "notes": "Construct and anchors reviewed.",
        "scenario_digest": scenario_digest(scenario),
    }
    event.update(overrides)
    return event


def _reviewed_fixture_manifest(source_dir: Path) -> dict:
    manifest = build_manifest(source_dir, track="core", language="en")
    scenarios = _load_fixture_scenarios(source_dir)
    for scenario in scenarios:
        item = manifest["items"][scenario["scenario_id"]]
        item["author_ids"] = ["fixture-author"]
        item["review_events"] = [_review_event(scenario)]
        item["status"] = "reviewed"
    return manifest


def _load_fixture_scenarios(source_dir: Path) -> list[dict]:
    return [
        json.loads(line)
        for path in sorted(source_dir.glob("*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _write_manifest(path: Path, manifest: dict) -> Path:
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_v07_manifest_starts_every_item_draft(v07_fixture_dir: Path) -> None:
    manifest = build_manifest(v07_fixture_dir, track="core", language="en")

    assert {item["status"] for item in manifest["items"].values()} == {"draft_unreviewed"}
    assert all(item["review_events"] == [] for item in manifest["items"].values())


def test_changed_digest_invalidates_review(v07_fixture_dir: Path) -> None:
    manifest = _reviewed_fixture_manifest(v07_fixture_dir)
    scenario_path = next(v07_fixture_dir.glob("*.jsonl"))
    scenarios = _load_fixture_scenarios(v07_fixture_dir)
    stale_item = manifest["items"][scenarios[0]["scenario_id"]]
    stale_item["status"] = "draft_unreviewed"
    scenarios[0]["initial_prompt"] = "This changed prompt invalidates review evidence."
    scenario_path.write_text(
        "".join(json.dumps(scenario) + "\n" for scenario in scenarios),
        encoding="utf-8",
    )
    manifest_path = _write_manifest(v07_fixture_dir / "review-status.json", manifest)

    result = validate_v07_review_manifest(v07_fixture_dir, manifest_path)

    assert result["stale_review_count"] == 1
    assert result["status_counts"]["draft_unreviewed"] == 1


@pytest.mark.parametrize(
    "stale_status",
    ["in_review", "changes_requested", "reviewed", "release_ready"],
)
def test_changed_digest_rejects_persisted_non_draft_status(
    v07_fixture_dir: Path, stale_status: str
) -> None:
    manifest = _reviewed_fixture_manifest(v07_fixture_dir)
    scenario_path = next(v07_fixture_dir.glob("*.jsonl"))
    scenarios = _load_fixture_scenarios(v07_fixture_dir)
    manifest["items"][scenarios[0]["scenario_id"]]["status"] = stale_status
    scenarios[0]["initial_prompt"] = "This changed prompt invalidates review evidence."
    scenario_path.write_text(
        "".join(json.dumps(scenario) + "\n" for scenario in scenarios),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="stale.*draft_unreviewed"):
        validate_v07_review_manifest(v07_fixture_dir, manifest)


def test_author_cannot_satisfy_independent_construct_review(v07_fixture_dir: Path) -> None:
    manifest = _reviewed_fixture_manifest(v07_fixture_dir)
    scenario = _load_fixture_scenarios(v07_fixture_dir)[0]
    author_events = [_review_event(scenario, conflict_disclosure="reviewer is the scenario author")]
    manifest["items"][scenario["scenario_id"]]["review_events"] = author_events
    manifest_path = _write_manifest(v07_fixture_dir / "review-status.json", manifest)

    assert derive_review_status(scenario, author_events) == "in_review"
    with pytest.raises(ValidationError, match="independent construct review"):
        validate_v07_review_manifest(v07_fixture_dir, manifest_path)


def test_v07_manifest_dispatch_and_digest_matched_regeneration(v07_fixture_dir: Path) -> None:
    manifest = _reviewed_fixture_manifest(v07_fixture_dir)
    manifest_path = _write_manifest(v07_fixture_dir / "review-status.json", manifest)

    result = validate_review_manifest(v07_fixture_dir, manifest_path)
    regenerated = build_manifest(
        v07_fixture_dir,
        track="core",
        language="en",
        existing_manifest=deepcopy(manifest),
    )

    assert result["status_counts"] == {"reviewed": 2}
    assert regenerated == manifest

    scenario_path = next(v07_fixture_dir.glob("*.jsonl"))
    scenarios = _load_fixture_scenarios(v07_fixture_dir)
    scenarios[0]["initial_prompt"] = "A digest-changing revision."
    scenario_path.write_text(
        "".join(json.dumps(scenario) + "\n" for scenario in scenarios), encoding="utf-8"
    )
    reset = build_manifest(
        v07_fixture_dir,
        track="core",
        language="en",
        existing_manifest=manifest,
    )
    assert reset["items"][scenarios[0]["scenario_id"]]["status"] == "draft_unreviewed"
    assert reset["items"][scenarios[0]["scenario_id"]]["review_events"] == []


def test_v07_schema_and_atomic_writer_accept_generated_manifest(
    v07_fixture_dir: Path, tmp_path: Path
) -> None:
    output = tmp_path / "review-status.json"

    manifest = write_manifest(
        v07_fixture_dir,
        output,
        track="core",
        language="en",
    )
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1] / "schemas" / "review-status-v0.2.schema.json"
        ).read_text(encoding="utf-8")
    )

    assert json.loads(output.read_text(encoding="utf-8")) == manifest
    Draft202012Validator(schema).validate(manifest)


def test_vietnamese_high_risk_requires_locale_and_specialist_reviews(
    tmp_path: Path, scenario_factory
) -> None:
    source_dir = tmp_path / "core" / "vi"
    source_dir.mkdir(parents=True)
    scenario = scenario_factory(
        benchmark_version="0.7",
        benchmark_track="core",
        scenario_id="review-vi-001",
        language="vi",
        risk_level="high",
        tags=[
            "concept-family-review-vi-001",
            "context-review-vi-001",
            "derivation-authored-new",
            "requires-cultural-review",
        ],
    )
    (source_dir / "dependency_boundaries.jsonl").write_text(
        json.dumps(scenario, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    manifest = build_manifest(source_dir, track="core", language="vi")
    item = manifest["items"][scenario["scenario_id"]]
    item["author_ids"] = ["fixture-author"]
    item["review_events"] = [
        _review_event(scenario),
        _review_event(
            scenario,
            review_type="locale",
            reviewer_id="reviewer-vi-001",
            reviewed_locale="vi-VN",
        ),
    ]
    item["status"] = "in_review"
    manifest_path = _write_manifest(source_dir / "review-status.json", manifest)

    result = validate_v07_review_manifest(source_dir, manifest_path)
    assert result["status_counts"] == {"in_review": 1}

    item["review_events"].append(
        _review_event(
            scenario,
            review_type="specialist_safety",
            reviewer_id="specialist-001",
        )
    )
    item["status"] = "reviewed"
    _write_manifest(manifest_path, manifest)
    result = validate_v07_review_manifest(source_dir, manifest_path)
    assert result["status_counts"] == {"reviewed": 1}

    item["review_events"].append(
        _review_event(scenario, review_type="release", reviewer_id="release-001")
    )
    item["status"] = "release_ready"
    _write_manifest(manifest_path, manifest)
    result = validate_v07_review_manifest(source_dir, manifest_path)
    assert result["status_counts"] == {"release_ready": 1}
