from __future__ import annotations

import importlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.validation import ValidationError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    module = importlib.import_module("humanai_impact_bench.v08_dataset")
    output = tmp_path_factory.mktemp("v08-parent") / "v0.8"
    index = module.prepare_v08(ROOT / "data/scenarios/v0.7", output)
    return module, output, index


def test_real_corpus_and_pilot_inventory(prepared):
    module, output, index = prepared
    records = module.load_v08_records(output)
    assert Counter(r["benchmark_track"] for r in records) == {"core": 2400, "agentic": 400}
    assert index["scenario_count"] == 2800
    pilot = json.loads((output / "pilot-index.json").read_text())["records"]
    assert len(pilot) == 64
    assert Counter(r["track"] for r in pilot) == {"core": 48, "agentic": 16}
    assert Counter(r["split"] for r in pilot) == {"calibration": 32, "public_evaluation": 32}
    assert len({r["category"] for r in pilot}) == 28
    assert len({r["matched_pair_id"] for r in pilot if r["track"] == "agentic"}) == 8
    assignments = json.loads((output / "split-index.json").read_text())["assignments"]
    assert module.select_pilot(list(reversed(records)), assignments) == sorted(
        r["scenario_id"] for r in pilot
    )


def test_migration_lineage_and_substance(prepared):
    module, output, _ = prepared
    records = module.load_v08_records(output)
    lineage = json.loads((output / "lineage-index.json").read_text())["entries"]
    source = {}
    for track in ["core", "agentic"]:
        for path in (ROOT / "data/scenarios/v0.7" / track / "en").glob("*.jsonl"):
            source.update(
                (r["scenario_id"], r)
                for r in (json.loads(line) for line in path.read_text().splitlines())
            )
    for row in records:
        entry = lineage[row["scenario_id"]]
        old = source[entry["source_scenario_id"]]
        assert record_digest(old) == entry["source_digest"]
        assert record_digest(row) == entry["scenario_digest"]
        normalized = deepcopy(row)
        normalized["benchmark_version"] = "0.7"
        normalized["scenario_id"] = old["scenario_id"]
        if "matched_pair_id" in normalized:
            normalized["matched_pair_id"] = old["matched_pair_id"]
        assert normalized == old


def test_preparation_is_idempotent_and_refuses_conflicts(prepared):
    module, output, _ = prepared
    before = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    module.prepare_v08(ROOT / "data/scenarios/v0.7", output)
    assert before == {
        str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()
    }
    extra = output / "unexpected.txt"
    extra.write_text("Do not overwrite user files")
    with pytest.raises(ValidationError, match="conflict|nonempty|existing"):
        module.prepare_v08(ROOT / "data/scenarios/v0.7", output)
    extra.unlink()
    with pytest.raises(ValidationError, match="overlap"):
        module.prepare_v08(ROOT / "data/scenarios/v0.7", ROOT / "data/scenarios/v0.7/new")


def test_selection_rejects_missing_families_and_pairs(prepared):
    module, output, _ = prepared
    records = module.load_v08_records(output)
    assignments = json.loads((output / "split-index.json").read_text())["assignments"]
    with pytest.raises(ValidationError, match="assignment|split"):
        module.select_pilot(records, {})
    removed = next(r for r in records if r["benchmark_track"] == "agentic")
    with pytest.raises(ValidationError, match="pair"):
        module.select_pilot([r for r in records if r != removed], assignments)


def test_materialize_checks_digests_and_single_track(prepared, tmp_path):
    module, output, _ = prepared
    selection = output / "pilot-index.json"
    dest = tmp_path / "core.jsonl"
    result = module.materialize_selection(output, selection, "core", dest)
    assert result["scenario_count"] == 48
    assert {json.loads(line)["benchmark_track"] for line in dest.read_text().splitlines()} == {
        "core"
    }
    changed = json.loads(selection.read_text())
    changed["records"][0]["scenario_digest"] = "0" * 64
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(changed))
    with pytest.raises(ValidationError, match="digest"):
        module.materialize_selection(output, bad, "core", tmp_path / "bad.jsonl")


def test_review_manifest_is_draft_only_and_digest_bound(prepared):
    _, output, _ = prepared
    from humanai_impact_bench.review import validate_v08_review_manifest

    directory = output / "core/en"
    manifest = json.loads((directory / "review-status.json").read_text())
    assert validate_v08_review_manifest(directory, manifest)["status_counts"] == {
        "draft_unreviewed": 2400
    }
    first = next(iter(manifest["items"].values()))
    first["scenario_digest"] = "0" * 64
    with pytest.raises(ValidationError, match="digest"):
        validate_v08_review_manifest(directory, manifest)


def test_materialize_rejects_forged_split(prepared, tmp_path):
    module, output, _ = prepared
    pilot = json.loads((output / "pilot-index.json").read_text())
    pilot["records"][0]["split"] = "invented-split"
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps(pilot))
    with pytest.raises(ValidationError, match="split"):
        module.materialize_selection(output, selection, "core", tmp_path / "selected.jsonl")
