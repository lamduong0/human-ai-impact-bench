import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml

from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.validation import load_scenarios
from scripts.generate_v07_review_manifests import build_manifest

ROOT = Path(__file__).resolve().parents[1]
CONFIGURATIONS = {
    "v0.7-core-en": ("core", "en", 2400, 24, 100),
    "v0.7-agentic-en": ("agentic", "en", 400, 4, 100),
    "v0.7-core-vi-preview": ("core", "vi", 400, 16, 25),
    "v0.7-agentic-vi-preview": ("agentic", "vi", 200, 4, 50),
}


def _configs():
    text = (ROOT / "huggingface/README.md").read_text()
    parts = text.split("\n---\n", 1)
    assert text.startswith("---\n") and len(parts) == 2
    metadata = yaml.safe_load(parts[0][4:])
    configs = metadata["configs"]
    assert len(configs) == len({c["config_name"] for c in configs})
    return {c["config_name"]: c for c in configs}


def test_v07_huggingface_routes_exact_configurations_and_current_draft_records():
    configs = _configs()
    assert {name for name in configs if name.startswith("v0.7")} == set(CONFIGURATIONS)
    total = 0
    for name, (track, language, count, categories, per_category) in CONFIGURATIONS.items():
        directory = ROOT / "data/scenarios/v0.7" / track / language
        route = f"data/scenarios/v0.7/{track}/{language}/*.jsonl"
        assert configs[name] == {
            "config_name": name,
            "data_files": [{"split": language, "path": route}],
        }
        paths = sorted(ROOT.glob(route))
        assert paths == sorted(directory.glob("*.jsonl"))
        assert len(paths) == categories
        records = [r for path in paths for r in load_scenarios(path)]
        assert len(records) == count
        assert Counter(r["category"] for r in records) == dict.fromkeys(
            (p.stem for p in paths), per_category
        )
        assert all(
            (r["benchmark_version"], r["benchmark_track"], r["language"])
            == ("0.7", track, language)
            for r in records
        )
        manifest = json.loads((directory / "review-status.json").read_text())
        assert manifest == build_manifest(directory, track=track, language=language)
        assert all(
            manifest["items"][r["scenario_id"]]
            == {
                "scenario_digest": record_digest(r),
                "status": "draft_unreviewed",
                "review_events": [],
            }
            for r in records
        )
        total += count
    assert total == 3400


def test_huggingface_v07_matches_frozen_configuration_index():
    root = ROOT / "data/scenarios/v0.7"
    index = json.loads((root / "configuration-index.json").read_text())
    configs = _configs()
    assert set(index["configurations"]) == set(CONFIGURATIONS)
    for name, (track, language, count, categories, per_category) in CONFIGURATIONS.items():
        summary = index["configurations"][name]
        assert (summary["benchmark_track"], summary["language"]) == (track, language)
        assert summary["scenario_count"] == count
        paths = sorted(ROOT.glob(configs[name]["data_files"][0]["path"]))
        assert summary["files"] == [
            {
                "path": str(path.relative_to(root)),
                "scenario_count": len(load_scenarios(path)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in paths
        ]
        assert len(paths) == categories
        assert summary["category_counts"] == dict.fromkeys((p.stem for p in paths), per_category)
        assert summary["language_counts"] == {language: count}
        assert summary["review_status_counts"] == {"draft_unreviewed": count}
        manifest = root / track / language / "review-status.json"
        assert summary["review_manifest"] == {
            "path": str(manifest.relative_to(root)),
            "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        }


def test_all_huggingface_routes_exclude_quarantine_and_preserve_historical_counts():
    configs = _configs()
    assert set(configs) == {f"v0.{i}" for i in range(1, 7)} | set(CONFIGURATIONS)
    counts = {}
    routed = set()
    for name, config in configs.items():
        paths = [path for entry in config["data_files"] for path in ROOT.glob(entry["path"])]
        assert paths and len(paths) == len(set(paths))
        assert not routed.intersection(paths)
        assert all(
            "pending-safety-review" not in path.parts and path.suffix == ".jsonl" for path in paths
        )
        routed.update(paths)
        counts[name] = sum(len(load_scenarios(path)) for path in paths)
    assert {name: counts[name] for name in counts if name not in CONFIGURATIONS} == {
        "v0.1": 16,
        "v0.2": 16,
        "v0.3": 200,
        "v0.4": 56,
        "v0.5": 400,
        "v0.6": 1200,
    }
    assert sum(counts.values()) == 5288
    assert sum(counts[f"v0.{i}"] for i in range(1, 5)) == 288


def test_v07_huggingface_declares_non_null_nested_list_features():
    text = (ROOT / "huggingface/README.md").read_text()
    metadata = yaml.safe_load(text.split("\n---\n", 1)[0][4:])
    infos = {entry["config_name"]: entry for entry in metadata.get("dataset_info", [])}
    assert set(infos) == set(CONFIGURATIONS)
    for name, (track, language, *_counts) in CONFIGURATIONS.items():
        features = {entry["name"]: entry for entry in infos[name]["features"]}
        records = [
            r
            for p in sorted((ROOT / "data/scenarios/v0.7" / track / language).glob("*.jsonl"))
            for r in load_scenarios(p)
        ]
        assert set(features) == set().union(
            *(r.keys() - {"_source_file", "_source_line"} for r in records)
        )
        persona = {entry["name"]: entry for entry in features["persona"]["struct"]}
        assert persona["vulnerability_factors"] == {
            "name": "vulnerability_factors",
            "list": "string",
        }
        for field in (
            "follow_up_prompts",
            "expected_behaviors",
            "failure_modes",
            "dimensions",
            "tags",
        ):
            assert features[field] == {"name": field, "list": "string"}
        if track == "agentic":
            assert features["prefill_messages"]["list"] == [
                {"name": "role", "dtype": "string"},
                {"name": "content", "dtype": "string"},
            ]
