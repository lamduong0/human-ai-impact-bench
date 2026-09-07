from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = json.loads(
    (ROOT / "configs" / "scenario-coverage-standard.json").read_text(encoding="utf-8")
)


def test_v07_core_english_coverage_arithmetic() -> None:
    core = COVERAGE["v0.7"]["core_en"]

    assert core["category_count"] == 24
    assert core["concept_families_per_category"] == 25
    assert core["contexts_per_family"] == 4
    assert core["records_per_category"] == 100
    assert core["total_records"] == 2400


def test_v07_core_vietnamese_preview_scope() -> None:
    preview = COVERAGE["v0.7"]["core_vi_preview"]

    assert preview["category_count"] == 16
    assert preview["records_per_category"] == 25
    assert preview["total_records"] == 400
    assert preview["blocks_english_milestone"] is False
