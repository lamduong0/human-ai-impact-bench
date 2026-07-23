from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from humanai_impact_bench.cli import main


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> Path:
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    return path


def test_validate_command_reports_summary(
    tmp_path: Path,
    scenario_factory: Callable[..., dict[str, Any]],
    capsys: Any,
) -> None:
    path = write_jsonl(
        tmp_path / "scenarios.jsonl",
        [scenario_factory(), scenario_factory(language="vi")],
    )

    exit_code = main(["validate", str(path)])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "valid": True,
        "scenario_count": 2,
        "languages": ["en", "vi"],
    }


def test_validate_command_accepts_scenario_directory(
    tmp_path: Path,
    scenario_factory: Callable[..., dict[str, Any]],
    capsys: Any,
) -> None:
    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir()
    write_jsonl(scenario_dir / "en.jsonl", [scenario_factory()])
    write_jsonl(scenario_dir / "vi.jsonl", [scenario_factory(language="vi")])

    exit_code = main(["validate", str(scenario_dir)])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "valid": True,
        "scenario_count": 2,
        "languages": ["en", "vi"],
    }


def test_score_command_emits_json(
    tmp_path: Path,
    annotation_factory: Callable[..., dict[str, Any]],
    capsys: Any,
) -> None:
    path = write_jsonl(tmp_path / "annotations.jsonl", [annotation_factory()])

    exit_code = main(["score", str(path), "--pretty"])

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert result[0]["model"] == "model-a"
    assert result[0]["annotation_count"] == 1
    assert "\n  {" in captured.out


def test_command_reports_validation_errors_to_stderr(
    tmp_path: Path,
    capsys: Any,
) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text("not json\n", encoding="utf-8")

    exit_code = main(["score", str(path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "error:" in captured.err
    assert "invalid JSON" in captured.err
