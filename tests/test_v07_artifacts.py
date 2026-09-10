from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

import pytest

from humanai_impact_bench.validation import ValidationError
from scripts.generate_v07_review_manifests import build_manifest
from scripts.v07_artifacts import (
    build_configuration_index,
    build_lineage_index,
    build_split_index,
    load_v07_configuration,
    record_digest,
    single_tag,
)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _scenario_set_digest(records: list[dict]) -> str:
    ordered = sorted(
        records,
        key=lambda record: (
            record["language"],
            record["category"],
            record["scenario_id"],
        ),
    )
    payload = json.dumps(
        ordered,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture
def v07_small_fixture(tmp_path: Path, scenario_factory) -> Path:
    root = tmp_path / "v0.7"
    source = scenario_factory(
        benchmark_version="0.6",
        scenario_id="source-001",
        category="dependency_boundaries",
    )
    _write_jsonl(
        tmp_path / "v0.6" / "en" / "dependency_boundaries.jsonl",
        [source],
    )

    configuration_specs = (
        ("core", "en", "dependency_boundaries"),
        ("core", "vi", "dependency_boundaries"),
        ("agentic", "en", "trajectory_recovery_and_correction"),
        ("agentic", "vi", "trajectory_recovery_and_correction"),
    )
    configuration_records = {}
    for track, language, category in configuration_specs:
        records = []
        for index in range(25):
            scenario_id = f"v07-{track}-{language}-{index:02d}"
            tags = [
                f"concept-family-{track}-{index:02d}",
                f"context-{track}-{index:02d}",
                "derivation-authored-new",
            ]
            if track == "core" and language == "en" and index == 0:
                tags = [
                    "concept-family-core-00",
                    "context-core-00",
                    "derivation-adapted",
                    "source-version-v0-6",
                    "source-scenario-source-001",
                ]
            overrides = {
                "benchmark_version": "0.7",
                "benchmark_track": track,
                "scenario_id": scenario_id,
                "language": language,
                "category": category,
                "tags": tags,
            }
            if track == "agentic":
                overrides.update(
                    locale="en-US" if language == "en" else "vi-VN",
                    protocol_mode="control",
                    matched_pair_id=f"{track}-{language}-{index:02d}",
                )
            records.append(scenario_factory(**overrides))

        configuration_records[(track, language)] = records
        source_dir = root / track / language
        _write_jsonl(source_dir / f"{category}.jsonl", records)
        _write_json(
            source_dir / "review-status.json",
            build_manifest(source_dir, track=track, language=language),
        )

    _write_json(root / "lineage-index.json", build_lineage_index(root))
    _write_json(root / "split-index.json", build_split_index(root))
    _write_json(
        root / "overlap-audit.json",
        {
            "audit_version": "0.1",
            "benchmark_version": "0.7",
            "candidate_count": 0,
            "candidates": [],
            "configuration_sha256": {
                "v0.7-agentic-en": _scenario_set_digest(configuration_records[("agentic", "en")]),
                "v0.7-agentic-vi-preview": _scenario_set_digest(
                    configuration_records[("agentic", "vi")]
                ),
                "v0.7-core-en": _scenario_set_digest(configuration_records[("core", "en")]),
                "v0.7-core-vi-preview": _scenario_set_digest(configuration_records[("core", "vi")]),
            },
            "resolutions": [],
            "scenario_count": 100,
            "valid": True,
        },
    )
    return root


def test_shared_primitives_load_validate_and_digest(v07_small_fixture: Path) -> None:
    records = load_v07_configuration("core", "en", v07_small_fixture)

    assert len(records) == 25
    assert single_tag(records[0], "concept-family-") == "core-00"
    assert record_digest(records[0]) == (
        "33396d7745aca39db9c22b5a00b3c40c6fbfd8ae94465cd6b97793e57de0ccdc"
    )


def test_lineage_binds_adapted_source_and_rejects_invalid_source_tags(
    v07_small_fixture: Path,
) -> None:
    index = build_lineage_index(v07_small_fixture)
    adapted = next(item for item in index["items"] if item["derivation"] == "adapted")

    assert adapted["source"] == {
        "benchmark_version": "0.6",
        "language": "en",
        "path": "v0.6/en/dependency_boundaries.jsonl",
        "scenario_id": "source-001",
        "scenario_sha256": "82543eef72930f02a8d137b93c48d91bf723e682ae08b5532197d5fe0b76f49b",
    }
    assert adapted["target"]["scenario_sha256"] == record_digest(
        load_v07_configuration("core", "en", v07_small_fixture)[0]
    )

    path = v07_small_fixture / "core" / "vi" / "dependency_boundaries.jsonl"
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    record["tags"].append("source-version-v0-6")
    _write_jsonl(path, [record])
    with pytest.raises(ValidationError, match="authored-new.*source"):
        build_lineage_index(v07_small_fixture)


def test_split_assignment_keeps_concept_family_together(v07_small_fixture: Path) -> None:
    index = build_split_index(v07_small_fixture)
    by_family: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for item in index["items"]:
        family = (item["benchmark_track"], item["category"], item["concept_family_id"])
        by_family[family].add(item["split"])

    assert all(len(splits) == 1 for splits in by_family.values())
    assert index["split_counts"] == {"calibration": 80, "public_evaluation": 20}
    assert index["selection_rule"] == (
        "Within each track/category, sort the 25 concept-family IDs. Assign the first 20 "
        "families to `calibration` and the final 5 to `public_evaluation`. Every context, "
        "mode, and language record for a family inherits that assignment."
    )


def _translate_first_record(root: Path, track: str = "core", *, same_id: bool = False):
    category = "dependency_boundaries" if track == "core" else "trajectory_recovery_and_correction"
    source = load_v07_configuration(track, "en", root)[0]
    path = root / track / "vi" / f"{category}.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    target = records[0]
    if same_id:
        target["scenario_id"] = source["scenario_id"]
    target["tags"] = [
        tag for tag in source["tags"] if not tag.startswith(("derivation-", "source-"))
    ] + [
        "derivation-adapted",
        "source-version-v0-7",
        "source-language-en",
        f"source-scenario-{source['scenario_id']}",
        "requires-cultural-review",
    ]
    _write_jsonl(path, records)
    return path, records, source


@pytest.mark.parametrize("track", ["core", "agentic"])
@pytest.mark.parametrize("same_id", [False, True])
def test_v07_translation_lineage_binds_same_track_english_source(
    v07_small_fixture: Path, track: str, same_id: bool
) -> None:
    path, records, source = _translate_first_record(v07_small_fixture, track, same_id=same_id)
    index = build_lineage_index(v07_small_fixture)
    translated = next(
        item
        for item in index["items"]
        if item["target"]["language"] == "vi"
        and item["target"]["benchmark_track"] == track
        and item["target"]["scenario_id"] == records[0]["scenario_id"]
    )
    assert translated["source"] == {
        "benchmark_version": "0.7",
        "benchmark_track": track,
        "language": "en",
        "path": f"v0.7/{track}/en/{path.name}",
        "scenario_id": source["scenario_id"],
        "scenario_sha256": record_digest(source),
    }
    if track == "core":
        ancestor = next(
            item
            for item in index["items"]
            if item["target"]["language"] == "en"
            and item["target"]["scenario_id"] == source["scenario_id"]
        )
        assert ancestor["source"]["benchmark_version"] == "0.6"
        assert ancestor["source"]["scenario_id"] == "source-001"


@pytest.mark.parametrize(
    "language_tags", [[], ["source-language-vi"], ["source-language-en", "source-language-vi"]]
)
def test_v07_translation_requires_exact_explicit_english_source_language(
    v07_small_fixture: Path, language_tags: list[str]
) -> None:
    path, records, _ = _translate_first_record(v07_small_fixture)
    records[0]["tags"] = [
        t for t in records[0]["tags"] if not t.startswith("source-language-")
    ] + language_tags
    _write_jsonl(path, records)
    with pytest.raises(ValidationError, match="source-language"):
        build_lineage_index(v07_small_fixture)


@pytest.mark.parametrize("source_id", ["v07-agentic-en-00", "v07-core-vi-00"])
def test_v07_translation_rejects_cross_track_or_self_source(
    v07_small_fixture: Path, source_id: str
) -> None:
    path, records, _ = _translate_first_record(v07_small_fixture)
    records[0]["tags"] = [t for t in records[0]["tags"] if not t.startswith("source-scenario-")] + [
        f"source-scenario-{source_id}"
    ]
    _write_jsonl(path, records)
    with pytest.raises(ValidationError, match="resolve to exactly one"):
        build_lineage_index(v07_small_fixture)


def test_v07_translation_rejects_an_english_back_edge_and_cycle(v07_small_fixture: Path) -> None:
    _translate_first_record(v07_small_fixture)
    path = v07_small_fixture / "core/en/dependency_boundaries.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[0]["tags"] = [
        "concept-family-core-00",
        "context-core-00",
        "derivation-adapted",
        "source-version-v0-7",
        "source-language-vi",
        "source-scenario-v07-core-vi-00",
    ]
    _write_jsonl(path, records)
    with pytest.raises(ValidationError, match="Vietnamese target"):
        build_lineage_index(v07_small_fixture)


@pytest.mark.parametrize(
    "field,value",
    [("benchmark_version", "0.6"), ("language", "vi"), ("benchmark_track", "agentic")],
)
def test_v07_translation_rejects_mismatched_source_metadata(
    v07_small_fixture: Path, field: str, value: str
) -> None:
    path, records, _ = _translate_first_record(v07_small_fixture)
    source_path = v07_small_fixture / "core/en" / path.name
    sources = [json.loads(line) for line in source_path.read_text().splitlines()]
    sources[0][field] = value
    _write_jsonl(source_path, sources)
    with pytest.raises(ValidationError):
        build_lineage_index(v07_small_fixture)


def test_v07_translation_does_not_allow_other_source_versions(v07_small_fixture: Path) -> None:
    path, records, _ = _translate_first_record(v07_small_fixture)
    records[0]["tags"] = [
        t.replace("source-version-v0-7", "source-version-v0-8") for t in records[0]["tags"]
    ]
    _write_jsonl(path, records)
    with pytest.raises(ValidationError, match="source version"):
        build_lineage_index(v07_small_fixture)


def test_source_language_tag_cannot_be_used_on_authored_new_records(
    v07_small_fixture: Path,
) -> None:
    path = v07_small_fixture / "core/vi/dependency_boundaries.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[0]["tags"].append("source-language-en")
    _write_jsonl(path, records)
    with pytest.raises(ValidationError, match="authored-new.*source"):
        build_lineage_index(v07_small_fixture)


def test_historical_sources_cannot_override_their_same_language_rule(
    v07_small_fixture: Path,
) -> None:
    path = v07_small_fixture / "core/en/dependency_boundaries.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[0]["tags"].append("source-language-vi")
    _write_jsonl(path, records)
    with pytest.raises(ValidationError, match="source-language.*reserved"):
        build_lineage_index(v07_small_fixture)


def test_split_assignment_requires_25_families_per_track_category(
    v07_small_fixture: Path,
) -> None:
    path = v07_small_fixture / "core" / "en" / "dependency_boundaries.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[0]["tags"][0] = "concept-family-core-25"
    _write_jsonl(path, records)

    with pytest.raises(ValidationError, match="exactly 25 concept families"):
        build_split_index(v07_small_fixture)


def test_split_assignment_rejects_invalid_lineage_tags(v07_small_fixture: Path) -> None:
    path = v07_small_fixture / "core" / "en" / "dependency_boundaries.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[0]["tags"].remove("derivation-adapted")
    _write_jsonl(path, records)

    with pytest.raises(ValidationError, match="exactly one non-empty derivation tag"):
        build_split_index(v07_small_fixture)


def test_lineage_rejects_source_record_with_mismatched_benchmark_version(
    v07_small_fixture: Path,
) -> None:
    path = v07_small_fixture.parent / "v0.6" / "en" / "dependency_boundaries.jsonl"
    source = json.loads(path.read_text(encoding="utf-8"))
    source.update(
        benchmark_version="0.5",
        locale="en-US",
        protocol_mode="continuous",
        matched_pair_id="source-pair-001",
    )
    _write_jsonl(path, [source])

    with pytest.raises(ValidationError, match="source.*benchmark_version.*0.6"):
        build_lineage_index(v07_small_fixture)


def test_configuration_index_is_reproducible_from_complete_fixture(
    v07_small_fixture: Path,
) -> None:
    first = build_configuration_index(v07_small_fixture)
    second = build_configuration_index(v07_small_fixture)

    assert first == second
    assert first["scenario_count"] == 100
    assert first["language_counts"] == {"en": 50, "vi": 50}
    assert first["review_status_counts"] == {"draft_unreviewed": 100}
    assert set(first["configurations"]) == {
        "v0.7-agentic-en",
        "v0.7-agentic-vi-preview",
        "v0.7-core-en",
        "v0.7-core-vi-preview",
    }
    assert first["configurations"]["v0.7-core-en"]["files"] == [
        {
            "path": "core/en/dependency_boundaries.jsonl",
            "scenario_count": 25,
            "sha256": "5f23fcadbedc4e0b0ae8fe5dea214c94513e3365b4307c1193d88bcaf4cb478e",
        }
    ]


@pytest.mark.parametrize(
    "artifact", ["lineage-index.json", "split-index.json", "overlap-audit.json"]
)
def test_configuration_index_refuses_missing_required_artifact(
    v07_small_fixture: Path,
    artifact: str,
) -> None:
    (v07_small_fixture / artifact).unlink()

    with pytest.raises(ValidationError, match="required artifact"):
        build_configuration_index(v07_small_fixture)


def test_configuration_index_refuses_inconsistent_derived_artifact(
    v07_small_fixture: Path,
) -> None:
    path = v07_small_fixture / "lineage-index.json"
    lineage = json.loads(path.read_text(encoding="utf-8"))
    changed = deepcopy(lineage)
    changed["items"][0]["target"]["scenario_sha256"] = "0" * 64
    _write_json(path, changed)

    with pytest.raises(ValidationError, match="lineage.*current scenarios"):
        build_configuration_index(v07_small_fixture)


def test_configuration_index_refuses_stale_draft_review_digest(
    v07_small_fixture: Path,
) -> None:
    path = v07_small_fixture / "core" / "en" / "review-status.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["items"]["v07-core-en-00"]["scenario_digest"] = "0" * 64
    _write_json(path, manifest)

    with pytest.raises(ValidationError, match="review digest.*current scenario"):
        build_configuration_index(v07_small_fixture)


def test_configuration_index_refuses_malformed_overlap_audit(
    v07_small_fixture: Path,
) -> None:
    _write_json(
        v07_small_fixture / "overlap-audit.json",
        {"benchmark_version": "0.7", "valid": True},
    )

    with pytest.raises(ValidationError, match="overlap audit.*required fields"):
        build_configuration_index(v07_small_fixture)


def test_configuration_index_refuses_stale_overlap_audit(
    v07_small_fixture: Path,
) -> None:
    path = v07_small_fixture / "overlap-audit.json"
    audit = json.loads(path.read_text(encoding="utf-8"))
    audit["configuration_sha256"]["v0.7-core-en"] = "0" * 64
    _write_json(path, audit)

    with pytest.raises(ValidationError, match="overlap audit.*current scenarios"):
        build_configuration_index(v07_small_fixture)


def test_configuration_index_refuses_unresolved_overlap_candidate(
    v07_small_fixture: Path,
) -> None:
    path = v07_small_fixture / "overlap-audit.json"
    audit = json.loads(path.read_text(encoding="utf-8"))
    audit["candidate_count"] = 1
    audit["candidates"] = [{"candidate_id": "candidate-001"}]
    _write_json(path, audit)

    with pytest.raises(ValidationError, match="overlap audit.*invalid.*contract"):
        build_configuration_index(v07_small_fixture)
