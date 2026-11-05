from __future__ import annotations

import json
from pathlib import Path

from humanai_impact_bench.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_cli_materializes_one_track_without_mutating_corpus(tmp_path, capsys):
    result = main(
        [
            "prepare-v08",
            "--source",
            str(ROOT / "data/scenarios/v0.7"),
            "--output",
            str(tmp_path / "v08"),
        ]
    )
    assert result == 0
    assert (tmp_path / "v08/pilot-index.json").exists()
    capsys.readouterr()
    result = main(
        [
            "materialize-pilot",
            "--dataset",
            str(tmp_path / "v08"),
            "--track",
            "agentic",
            "--output",
            str(tmp_path / "pilot.jsonl"),
        ]
    )
    assert result == 0
    rows = [json.loads(line) for line in (tmp_path / "pilot.jsonl").read_text().splitlines()]
    assert len(rows) == 16
    assert {row["benchmark_track"] for row in rows} == {"agentic"}


def test_cli_invalid_study_is_an_actionable_error(tmp_path, capsys):
    manifest = tmp_path / "bad.json"
    manifest.write_text("{}")
    result = main(["run-study", "--manifest", str(manifest), "--output", str(tmp_path / "out")])
    assert result == 2
    assert "error:" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
