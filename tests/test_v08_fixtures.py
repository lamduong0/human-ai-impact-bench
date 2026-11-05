from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.quality import load_fixtures, validate_fixture
from humanai_impact_bench.v08_dataset import load_v08_records
from humanai_impact_bench.validation import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data/diagnostics/v0.8/fixtures.jsonl"


@pytest.fixture(scope="module")
def fixture_rows():
    return load_fixtures(FIXTURES, load_v08_records(ROOT / "data/scenarios/v0.8"))


def test_fixture_inventory(fixture_rows):
    assert len(fixture_rows) == 192
    assert {f["origin"] for f in fixture_rows} == {"synthetic_authored"}
    assert {f["split"] for f in fixture_rows} == {"calibration"}
    assert len({f["scenario_id"] for f in fixture_rows}) == 32
    assert all(len(f["candidate_messages"]) == 3 for f in fixture_rows)


def test_fixture_schema_and_text_diversity(fixture_rows):
    validator = Draft202012Validator(
        json.loads((ROOT / "schemas/judge-fixture-v0.8.schema.json").read_text())
    )
    useful = []
    for fixture in fixture_rows:
        validator.validate(fixture)
        if fixture["variant"] == "useful":
            useful.append(tuple(m["content"] for m in fixture["candidate_messages"]))
    # Paired protocols share context; distinct categories must have substantive continuations.
    assert len(set(useful)) >= 28


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda f: f.update(split="public_evaluation"), "calibration"),
        (lambda f: f.update(scenario_digest="a" * 64), "digest"),
        (lambda f: f["candidate_messages"].pop(), "continuation"),
        (lambda f: f.update(judge_prompt="This is the useful variant"), "fields"),
        (lambda f: f["context"]["user_messages"].__setitem__(0, "Invented user turn"), "context"),
    ],
)
def test_fixture_rejects_misbound_data(fixture_rows, mutation, match):
    fixture = deepcopy(fixture_rows[0])
    scenarios = {s["scenario_id"]: s for s in load_v08_records(ROOT / "data/scenarios/v0.8")}
    scenario = scenarios[fixture["scenario_id"]]
    assert fixture["scenario_digest"] == record_digest(scenario)
    mutation(fixture)
    with pytest.raises(ValidationError, match=match):
        validate_fixture(fixture, scenario)


def test_fixture_sources_are_only_calibration_pilot(fixture_rows):
    pilot = json.loads((ROOT / "data/scenarios/v0.8/pilot-index.json").read_text())
    expected = {r["scenario_id"] for r in pilot["records"] if r["split"] == "calibration"}
    assert {f["scenario_id"] for f in fixture_rows} == expected


def test_hypotheses_reference_valid_siblings(fixture_rows):
    by_id = {f["fixture_id"]: f for f in fixture_rows}
    for fixture in fixture_rows:
        for hypothesis in fixture["hypotheses"]:
            sibling = by_id[hypothesis["other_fixture_id"]]
            assert sibling["scenario_id"] == fixture["scenario_id"]
            assert sibling["fixture_id"] != fixture["fixture_id"]


def test_formatting_is_exact_text_invariance(fixture_rows):
    by_id = {f["fixture_id"]: f for f in fixture_rows}
    for fixture in fixture_rows:
        if fixture["variant"] != "formatting":
            continue
        useful = by_id[f"{fixture['scenario_id']}--useful"]
        for left, right in zip(
            fixture["candidate_messages"], useful["candidate_messages"], strict=True
        ):
            assert " ".join(left["content"].split()) == " ".join(right["content"].split())


def test_fixtures_cannot_ignore_frozen_pilot_source_digest(tmp_path, fixture_rows):
    import hashlib
    import shutil

    target = tmp_path / "data/diagnostics/v0.8"
    target.mkdir(parents=True)
    dataset = tmp_path / "data/scenarios/v0.8"
    dataset.mkdir(parents=True)
    for name in ("pilot-index.json", "split-index.json"):
        shutil.copyfile(ROOT / "data/scenarios/v0.8" / name, dataset / name)
    shutil.copyfile(FIXTURES.parent / "manifest.json", target / "manifest.json")
    scenarios = load_v08_records(ROOT / "data/scenarios/v0.8")
    by_id = {r["scenario_id"]: r for r in scenarios}
    changed = fixture_rows[0]["scenario_id"]
    by_id[changed]["title"] = "Unregistered source edit"
    rows = deepcopy(fixture_rows)
    for fixture in rows:
        if fixture["scenario_id"] == changed:
            fixture["scenario_digest"] = record_digest(by_id[changed])
    blob = "".join(json.dumps(f) + "\n" for f in rows).encode()
    (target / "fixtures.jsonl").write_bytes(blob)
    manifest = json.loads((target / "manifest.json").read_text())
    manifest["fixtures_sha256"] = hashlib.sha256(blob).hexdigest()
    (target / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValidationError, match="pilot.*digest|digest.*pilot"):
        load_fixtures(target / "fixtures.jsonl", scenarios)


def test_fixture_manifest_cannot_claim_human_gold(tmp_path, fixture_rows):
    import shutil

    target = tmp_path / "data/diagnostics/v0.8"
    target.mkdir(parents=True)
    dataset = tmp_path / "data/scenarios/v0.8"
    dataset.mkdir(parents=True)
    for name in ("pilot-index.json", "split-index.json"):
        shutil.copyfile(ROOT / "data/scenarios/v0.8" / name, dataset / name)
    shutil.copyfile(FIXTURES, target / "fixtures.jsonl")
    manifest = json.loads((FIXTURES.parent / "manifest.json").read_text())
    manifest["human_review"] = "approved"
    (target / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValidationError, match="provenance"):
        load_fixtures(target / "fixtures.jsonl", load_v08_records(ROOT / "data/scenarios/v0.8"))
