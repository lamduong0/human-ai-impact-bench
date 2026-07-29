from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from humanai_impact_bench.validation import ValidationError
from scripts import generate_v06_source_inventory

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "data" / "scenarios" / "v0.6" / "source-inventory.json"


def test_v06_source_inventory_matches_generator() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))

    assert inventory == generate_v06_source_inventory.build_inventory()


def test_v06_source_inventory_is_complete_and_review_transparent() -> None:
    inventory = generate_v06_source_inventory.build_inventory()

    assert inventory["target_benchmark_version"] == "0.6"
    assert inventory["source_versions"] == ["0.1", "0.2", "0.3", "0.4"]
    assert inventory["source_record_count"] == 288
    assert inventory["category_count"] == 24
    assert inventory["review_status_counts"] == {
        "maintainer_reviewed": 256,
        "no_review_manifest": 32,
    }
    assert len(inventory["items"]) == 288
    assert len({item["source_key"] for item in inventory["items"]}) == 288
    assert all(len(item["content_sha256"]) == 64 for item in inventory["items"])


def test_v06_source_inventory_rejects_invalid_review_provenance(
    tmp_path: Path,
) -> None:
    source_dir = ROOT / "data" / "scenarios" / "v0.4"
    for source_path in source_dir.glob("*.jsonl"):
        shutil.copy(source_path, tmp_path / source_path.name)
    manifest = json.loads((source_dir / "review-status.json").read_text(encoding="utf-8"))
    scenario_id = next(iter(manifest["items"]))
    manifest["items"][scenario_id]["status"] = "not-a-review-status"
    (tmp_path / "review-status.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="unknown status"):
        generate_v06_source_inventory._review_statuses(tmp_path)
