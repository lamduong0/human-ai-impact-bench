from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from humanai_impact_bench.review import validate_v08_review_manifest
from humanai_impact_bench.v08_dataset import load_v08_records, scenario_set_digest

ROOT = Path(__file__).resolve().parents[1]


def _metadata():
    text = (ROOT / "huggingface/README.md").read_text()
    return yaml.safe_load(text.split("\n---\n", 1)[0][4:])


def test_v08_huggingface_routes_exact_english_scopes_and_draft_manifests():
    metadata = _metadata()
    configs = {c["config_name"]: c for c in metadata["configs"]}
    assert {name for name in configs if name.startswith("v0.8")} == {
        "v0.8-core-en",
        "v0.8-agentic-en",
    }
    root = ROOT / "data/scenarios/v0.8"
    index = json.loads((root / "configuration-index.json").read_text())
    for track, count in [("core", 2400), ("agentic", 400)]:
        name = f"v0.8-{track}-en"
        assert configs[name]["data_files"] == [
            {"split": "en", "path": f"data/scenarios/v0.8/{track}/en/*.jsonl"}
        ]
        records = load_v08_records(root, track)
        assert len(records) == count
        assert scenario_set_digest(records) == index["configurations"][name]["scenario_digest"]
        review = validate_v08_review_manifest(
            root / track / "en", root / track / "en/review-status.json"
        )
        assert review["status_counts"] == {"draft_unreviewed": count}


def test_v08_declares_features_for_every_field_and_empty_nested_lists():
    metadata = _metadata()
    infos = {i["config_name"]: i for i in metadata["dataset_info"]}
    for track in ["core", "agentic"]:
        features = {f["name"]: f for f in infos[f"v0.8-{track}-en"]["features"]}
        rows = load_v08_records(ROOT / "data/scenarios/v0.8", track)
        assert set(features) == set().union(*(r.keys() for r in rows))
        persona = {f["name"]: f for f in features["persona"]["struct"]}
        assert persona["vulnerability_factors"]["list"] == "string"
        if track == "agentic":
            assert features["prefill_messages"]["list"] == [
                {"name": "role", "dtype": "string"},
                {"name": "content", "dtype": "string"},
            ]


@pytest.mark.parametrize(("track", "count"), [("core", 2400), ("agentic", 400)])
def test_v08_actual_huggingface_local_loading(tmp_path, track, count):
    datasets = pytest.importorskip("datasets")
    bundle = tmp_path / "publication"
    bundle.mkdir()
    (bundle / "README.md").write_bytes((ROOT / "huggingface/README.md").read_bytes())
    (bundle / "data").symlink_to(ROOT / "data", target_is_directory=True)
    data = datasets.load_dataset(
        str(bundle), name=f"v0.8-{track}-en", split="en", cache_dir=str(tmp_path / "hf-cache")
    )
    assert len(data) == count
    assert set(data["benchmark_version"]) == {"0.8"}
    assert set(data["benchmark_track"]) == {track}
    assert set(data["language"]) == {"en"}
    assert data.features["persona"]["vulnerability_factors"].feature.dtype == "string"
    if track == "agentic":
        assert data.features["prefill_messages"].feature["role"].dtype == "string"
        assert sum(row["protocol_mode"] == "control" for row in data) == 200
