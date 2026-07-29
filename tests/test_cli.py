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
    monkeypatch: Any,
) -> None:
    path = write_jsonl(
        tmp_path / "scenarios.jsonl",
        [scenario_factory(), scenario_factory(language="vi")],
    )

    monkeypatch.chdir(tmp_path)
    exit_code = main(["validate", path.name])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "valid": True,
        "source": str(path.resolve()),
        "source_is_directory": False,
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
        "source": str(scenario_dir.resolve()),
        "source_is_directory": True,
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


def _clustered_scenarios(
    scenario_factory: Callable[..., dict[str, Any]],
    concepts: int,
    contexts: int,
) -> list[dict[str, Any]]:
    return [
        scenario_factory(
            scenario_id=f"concept-{concept}-context-{context}",
            tags=[f"concept-c{concept}"],
        )
        for concept in range(concepts)
        for context in range(contexts)
    ]


def test_cluster_diagnostics_reports_effective_records(
    tmp_path: Path,
    scenario_factory: Callable[..., dict[str, Any]],
    capsys: Any,
) -> None:
    scenarios = _clustered_scenarios(scenario_factory, concepts=4, contexts=5)
    scenarios_path = write_jsonl(tmp_path / "scenarios.jsonl", scenarios)
    # Identical scores inside each concept, different between concepts: the
    # maximum-clustering case, where 20 records carry 4 records of evidence.
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "model": "candidate",
                "scenario_results": {
                    f"{scenario['scenario_id']}:en": {
                        "overall_score": 50.0
                        + 10 * int(scenario["tags"][0].removeprefix("concept-c"))
                    }
                    for scenario in scenarios
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "cluster-diagnostics",
            "--report",
            str(report_path),
            "--scenarios",
            str(scenarios_path),
        ]
    )

    assert exit_code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["scenario_records"] == 20
    assert result["clusters"] == 4
    assert result["intraclass_correlation"] == 1.0
    assert result["design_effect"] == 5.0
    assert result["effective_records"] == 4.0


def test_cluster_diagnostics_reports_no_clustering_for_independent_records(
    tmp_path: Path,
    scenario_factory: Callable[..., dict[str, Any]],
    capsys: Any,
) -> None:
    scenarios = _clustered_scenarios(scenario_factory, concepts=6, contexts=1)
    scenarios_path = write_jsonl(tmp_path / "scenarios.jsonl", scenarios)
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "model": "candidate",
                "scenario_results": {
                    f"{scenario['scenario_id']}:en": {"overall_score": 40.0 + 5 * index}
                    for index, scenario in enumerate(scenarios)
                },
            }
        ),
        encoding="utf-8",
    )

    argv = ["cluster-diagnostics", "--report", str(report_path), "--scenarios", str(scenarios_path)]
    assert main(argv) == 0

    result = json.loads(capsys.readouterr().out)
    # One record per cluster carries no within-cluster information, so the
    # correction must be a no-op rather than a silent inflation.
    assert result["design_effect"] == 1.0
    assert result["effective_records"] == 6.0


def test_cluster_diagnostics_rejects_a_report_without_scenario_results(
    tmp_path: Path,
    scenario_factory: Callable[..., dict[str, Any]],
    capsys: Any,
) -> None:
    scenarios_path = write_jsonl(
        tmp_path / "scenarios.jsonl", [scenario_factory(tags=["concept-a"])]
    )
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"model": "candidate"}), encoding="utf-8")

    assert (
        main(
            [
                "cluster-diagnostics",
                "--report",
                str(report_path),
                "--scenarios",
                str(scenarios_path),
            ]
        )
        == 2
    )
    assert "no scenario_results" in capsys.readouterr().err
