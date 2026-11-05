"""Bounded, resumable automated studies with replayable local evidence.

Provider transports are the existing runner/judge transports. The ledger stores
requests and responses without authentication headers; verification checks their
internal consistency, not the authenticity of a provider's identity.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from humanai_impact_bench import api_protocols as api
from humanai_impact_bench import deployment as dep
from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.validation import ValidationError, validate_scenario

_PATH_FIELDS = ("dataset_root", "selection_path", "fixtures_path", "system_prompt_path")
_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def _positive(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"{label} must be a positive integer")
    return value


def _pairs(items: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in items:
        if key in result:
            raise ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode(text: str) -> Any:
    def invalid(value):
        raise ValidationError(f"non-finite JSON number: {value}")

    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            invalid(value)
        return number

    try:
        return json.loads(
            text, object_pairs_hook=_pairs, parse_constant=invalid, parse_float=finite
        )
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"invalid JSON: {exc}") from exc


def read_json(path: Path) -> Any:
    try:
        return _decode(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValidationError(f"cannot read artifact {path.name}: {exc}") from exc


def _read_jsonl(path: Path) -> list[dict]:
    try:
        rows = [
            _decode(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
    except OSError as exc:
        raise ValidationError(f"cannot read JSONL {path.name}: {exc}") from exc
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValidationError("JSONL artifacts must contain nonempty object rows")
    return rows


def confined_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValidationError("artifact path must be relative to the bundle root")
    if ".." in Path(relative).parts:
        raise ValidationError("artifact path traversal is forbidden")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValidationError("artifact path escapes bundle root")
    return path


def _write(path: Path, value: Any) -> None:
    dep._atomic_write_json(path, value)


def _artifact(root: Path, path: Path) -> dict:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _checked_artifact(root: Path, ref: dict) -> Path:
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise ValidationError("invalid artifact reference")
    path = confined_path(root, ref["path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValidationError(f"artifact digest mismatch or missing file: {ref['path']}")
    return path


def validate_study(manifest: dict) -> None:
    required = {
        "study_version",
        "study_id",
        *_PATH_FIELDS,
        "targets",
        "judges",
        "generation_replicates",
        "rating_replicates",
        "retry_attempts",
        "budget",
        "analysis_seed",
        "bootstrap_resamples",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValidationError("study manifest fields do not match the v0.8 contract")
    if manifest["study_version"] != "0.8" or not _ID.fullmatch(str(manifest["study_id"])):
        raise ValidationError("invalid study version or ID")
    for key in _PATH_FIELDS:
        if key in {"fixtures_path", "system_prompt_path"} and manifest[key] is None:
            continue
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise ValidationError(f"{key} requires an input path")
    for key in (
        "generation_replicates",
        "rating_replicates",
        "retry_attempts",
        "bootstrap_resamples",
    ):
        _positive(manifest[key], key)
    if manifest["bootstrap_resamples"] < 2:
        raise ValidationError("bootstrap requires at least two resamples")
    if isinstance(manifest["analysis_seed"], bool) or not isinstance(
        manifest["analysis_seed"], int
    ):
        raise ValidationError("analysis_seed must be an integer")
    if not isinstance(manifest["budget"], dict) or set(manifest["budget"]) != {
        "max_requests",
        "max_output_tokens",
    }:
        raise ValidationError("budget requires request and output-token caps")
    for key, value in manifest["budget"].items():
        _positive(value, f"budget.{key}")
    for group in ("targets", "judges"):
        configs = manifest[group]
        if not isinstance(configs, list) or not configs:
            raise ValidationError(f"{group} must name at least one configured model")
        ids = set()
        for config in configs:
            fields = {
                "id",
                "family",
                "base_url",
                "model",
                "max_tokens",
                "temperature",
                "api_key_env",
            }
            if group == "targets":
                fields.add("candidate_digest")
            optional = api.MODEL_OPTIONS | (api.JUDGE_OPTIONS if group == "judges" else set())
            if (
                not isinstance(config, dict)
                or not fields <= config.keys()
                or config.keys() - fields - optional
            ):
                raise ValidationError(f"{group} model configuration has invalid fields")
            api.validate_options(config, judge=group == "judges")
            if not isinstance(config["id"], str) or not _ID.fullmatch(config["id"]):
                raise ValidationError("invalid model configuration ID")
            if config["id"] in ids:
                raise ValidationError("duplicate model configuration ID")
            ids.add(config["id"])
            for key in ("family", "model"):
                if not isinstance(config[key], str) or not config[key].strip():
                    raise ValidationError(f"model configuration {key} is required")
            url = urlsplit(dep._validate_base_url(config["base_url"], "model endpoint"))
            if url.username or url.password or url.query or url.fragment:
                raise ValidationError(
                    "endpoint URLs cannot contain credentials, queries or fragments"
                )
            _positive(config["max_tokens"], "max_tokens")
            dep._validate_temperature(config["temperature"])
            if config["api_key_env"] is not None and (
                not isinstance(config["api_key_env"], str)
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", config["api_key_env"])
            ):
                raise ValidationError("api_key_env must name an environment variable")
            if group == "targets":
                dep._candidate_digest(config["candidate_digest"])


def _tag(record: dict, prefix: str) -> str:
    tags = [tag[len(prefix) :] for tag in record["tags"] if tag.startswith(prefix)]
    if len(tags) != 1:
        raise ValidationError(f"scenario requires exactly one {prefix} tag")
    return tags[0]


def plan_study(
    manifest: dict,
    scenarios: list[dict],
    fixtures: list[dict],
    *,
    selection: dict[str, dict] | None = None,
) -> dict:
    validate_study(manifest)
    if not scenarios:
        raise ValidationError("a study requires scenarios")
    by_id = {row["scenario_id"]: row for row in scenarios}
    if len(by_id) != len(scenarios):
        raise ValidationError("duplicate scenario identity")
    tasks = []
    counts = {"generation_requests": 0, "rating_requests": 0, "fixture_rating_requests": 0}
    output_tokens = 0
    frozen_digest = record_digest(manifest)

    def task(kind, row, **kwargs):
        chosen = (selection or {}).get(row["scenario_id"], {})
        item = {
            "kind": kind,
            "scenario_id": row["scenario_id"],
            "scenario_digest": record_digest(row),
            "track": row["benchmark_track"],
            "category": row["category"],
            "split": chosen.get("split", "unspecified"),
            "family_id": _tag(row, "concept-family-"),
            "context_id": _tag(row, "context-"),
            "matched_pair_id": row.get("matched_pair_id"),
            "protocol_mode": row.get("protocol_mode"),
            "target_id": None,
            "generation_replicate": None,
            "judge_id": None,
            "rating_replicate": None,
            "fixture_id": None,
            "dependency": None,
            **kwargs,
        }
        item["task_id"] = record_digest({"study": frozen_digest, **item})[:24]
        tasks.append(item)
        return item

    for row in sorted(scenarios, key=lambda r: r["scenario_id"]):
        if row["benchmark_version"] != "0.8" or row["language"] != "en":
            raise ValidationError("studies require English v0.8 scenarios")
        for target in manifest["targets"]:
            for generation in range(manifest["generation_replicates"]):
                gen = task(
                    "generation", row, target_id=target["id"], generation_replicate=generation
                )
                turns = 1 + len(row["follow_up_prompts"])
                counts["generation_requests"] += turns
                output_tokens += turns * target["max_tokens"]
                for judge in manifest["judges"]:
                    for rating in range(manifest["rating_replicates"]):
                        task(
                            "rating",
                            row,
                            target_id=target["id"],
                            generation_replicate=generation,
                            judge_id=judge["id"],
                            rating_replicate=rating,
                            dependency=gen["task_id"],
                        )
                        counts["rating_requests"] += 1
                        output_tokens += judge["max_tokens"]
    fixture_ids = set()
    for fixture in fixtures:
        if fixture["fixture_id"] in fixture_ids or fixture["scenario_id"] not in by_id:
            raise ValidationError("duplicate fixture or unknown fixture scenario")
        fixture_ids.add(fixture["fixture_id"])
        row = by_id[fixture["scenario_id"]]
        for judge in manifest["judges"]:
            for rating in range(manifest["rating_replicates"]):
                task(
                    "fixture_rating",
                    row,
                    judge_id=judge["id"],
                    rating_replicate=rating,
                    fixture_id=fixture["fixture_id"],
                )
                counts["fixture_rating_requests"] += 1
                output_tokens += judge["max_tokens"]
    requests = sum(counts.values()) * manifest["retry_attempts"]
    tokens = output_tokens * manifest["retry_attempts"]
    if (
        requests > manifest["budget"]["max_requests"]
        or tokens > manifest["budget"]["max_output_tokens"]
    ):
        raise ValidationError("planned worst-case execution exceeds the declared budget")
    return {
        **counts,
        "worst_case_requests": requests,
        "worst_case_output_tokens": tokens,
        "task_count": len(tasks),
        "tasks": tasks,
        "family_declarations": {
            group: {c["id"]: c["family"] for c in manifest[group]}
            for group in ("targets", "judges")
        },
        "self_judging_pairs": [
            [t["id"], j["id"]]
            for t in manifest["targets"]
            for j in manifest["judges"]
            if t["family"] == j["family"]
        ],
    }


def _load_inputs(manifest_path: Path, *, confined: bool = False) -> dict:
    manifest = read_json(manifest_path)
    validate_study(manifest)
    base = manifest_path.parent.resolve()
    paths = {}
    for key in _PATH_FIELDS:
        value = manifest[key]
        paths[key] = (
            (confined_path(base, value) if confined else (base / value).resolve())
            if value
            else None
        )
    root = paths["dataset_root"]
    records = []
    for path in sorted(root.glob("*/en/*.jsonl")):
        if confined and not path.resolve().is_relative_to(base):
            raise ValidationError("source file escapes bundle root")
        for row in _read_jsonl(path):
            validate_scenario(row)
            if row["benchmark_version"] != "0.8" or row["language"] != "en":
                raise ValidationError("only English v0.8 sources are permitted")
            if path.parent.parent.name != row["benchmark_track"]:
                raise ValidationError("scenario track does not match source directory")
            records.append(row)
    by_id = {row["scenario_id"]: row for row in records}
    if not records or len(records) != len(by_id):
        raise ValidationError("source scenarios are missing or duplicated")
    selection = read_json(paths["selection_path"])
    if selection.get("benchmark_version") != "0.8" or not selection.get("records"):
        raise ValidationError("selection must identify English v0.8 records")
    selected = {}
    split_path = root / "split-index.json"
    split_index = read_json(split_path)
    assignments = split_index.get("assignments") if isinstance(split_index, dict) else None
    if not isinstance(assignments, dict) or not assignments:
        raise ValidationError("a study requires nonempty inherited split assignments")
    for chosen in selection["records"]:
        sid = chosen.get("scenario_id")
        if sid in selected or sid not in by_id:
            raise ValidationError("selection has duplicate or unknown scenario IDs")
        row = by_id[sid]
        expected = {
            "scenario_digest": record_digest(row),
            "track": row["benchmark_track"],
            "category": row["category"],
            "family_id": _tag(row, "concept-family-"),
            "context_id": _tag(row, "context-"),
        }
        if any(chosen.get(key) != value for key, value in expected.items()):
            raise ValidationError("selection metadata does not match actual scenario")
        if chosen.get("split") not in {"calibration", "public_evaluation"}:
            raise ValidationError("selection has invalid split")
        family_key = "|".join([chosen["track"], chosen["category"], chosen["family_id"]])
        if assignments.get(family_key) != chosen["split"]:
            raise ValidationError("selection differs from inherited split")
        selected[sid] = chosen
    chosen_rows = [by_id[sid] for sid in sorted(selected)]
    pairs = {}
    for row in chosen_rows:
        if row["benchmark_track"] == "agentic":
            pairs.setdefault(row["matched_pair_id"], []).append(row)
    for pair in pairs.values():
        if len(pair) != 2 or {r["protocol_mode"] for r in pair} != {"control", "prefill_stress"}:
            raise ValidationError("selection contains an incomplete agentic pair")
        excluded = {"scenario_id", "protocol_mode", "prefill_messages", "tags"}
        if {k: v for k, v in pair[0].items() if k not in excluded} != {
            k: v for k, v in pair[1].items() if k not in excluded
        }:
            raise ValidationError("agentic pair shared inputs differ")
    fixtures = []
    if paths["fixtures_path"]:
        from humanai_impact_bench.quality import load_fixtures

        fixtures = load_fixtures(paths["fixtures_path"], chosen_rows)
        if any(selected[f["scenario_id"]]["split"] != "calibration" for f in fixtures):
            raise ValidationError("diagnostic fixtures must belong to calibration")
    system = paths["system_prompt_path"].read_text() if paths["system_prompt_path"] else None
    return {
        "manifest": manifest,
        "paths": paths,
        "records": records,
        "scenarios": chosen_rows,
        "selection": selected,
        "fixtures": fixtures,
        "system": system,
        "split_index": split_index,
    }


def _instrument() -> dict:
    package = Path(__file__).parent
    return {
        "judge_prompt_digests": {
            "core": dep._sha256_text(dep._JUDGE_SYSTEM_PROMPT),
            "agentic": dep._sha256_text(dep._V08_AGENTIC_JUDGE_SYSTEM_PROMPT),
        },
        "runtime_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(package.glob("*.py"))
        },
        "analysis_contract": "v0.8-automated-study-v1",
    }


def _identity(inputs: dict) -> str:
    # Paths are locators, not experimental parameters. Bind the actual input contents.
    return record_digest(
        {
            "manifest": {k: v for k, v in inputs["manifest"].items() if k not in _PATH_FIELDS},
            "records": inputs["records"],
            "selection": inputs["selection"],
            "fixtures": inputs["fixtures"],
            "system": inputs["system"],
            "split_index": inputs["split_index"],
            "instrument": _instrument(),
        }
    )


def _initialize(inputs: dict, root: Path) -> None:
    root.mkdir(parents=True)
    snapshot = root / "inputs"
    snapshot.mkdir()
    # Copy only the declared dataset source and indexes, never neighboring files.
    dataset_snapshot = snapshot / "data" / "scenarios" / "v0.8"
    shutil.copytree(
        inputs["paths"]["dataset_root"],
        dataset_snapshot,
        ignore=shutil.ignore_patterns(".*", "__pycache__"),
    )
    frozen = deepcopy(inputs["manifest"])
    frozen["dataset_root"] = "inputs/data/scenarios/v0.8"
    for key, name in (("selection_path", "selection.json"), ("system_prompt_path", "system.txt")):
        if inputs["paths"][key]:
            shutil.copyfile(inputs["paths"][key], snapshot / name)
            frozen[key] = f"inputs/{name}"
    if inputs["paths"]["fixtures_path"]:
        fixture_snapshot = snapshot / "data" / "diagnostics" / "v0.8"
        fixture_snapshot.mkdir(parents=True)
        shutil.copyfile(inputs["paths"]["fixtures_path"], fixture_snapshot / "fixtures.jsonl")
        shutil.copyfile(
            inputs["paths"]["fixtures_path"].parent / "manifest.json",
            fixture_snapshot / "manifest.json",
        )
        frozen["fixtures_path"] = "inputs/data/diagnostics/v0.8/fixtures.jsonl"
    _write(root / "study.json", frozen)
    frozen_inputs = _load_inputs(root / "study.json", confined=True)
    plan = plan_study(
        frozen,
        frozen_inputs["scenarios"],
        frozen_inputs["fixtures"],
        selection=frozen_inputs["selection"],
    )
    tasks = [
        {**task, "status": "pending", "attempts": [], "artifacts": {}} for task in plan["tasks"]
    ]
    state = {
        "state_version": "0.8",
        "manifest_digest": record_digest(frozen),
        "input_digest": _identity(frozen_inputs),
        "instrument": _instrument(),
        "tasks": tasks,
    }
    _write(root / "study-state.json", state)


def _fixture_transcript(scenario: dict, fixture: dict, system: str | None) -> dict:
    messages = [{"role": "system", "content": system}] if system is not None else []
    messages.extend(deepcopy(scenario.get("prefill_messages", [])))
    for prompt, response in zip(
        [scenario["initial_prompt"], *scenario["follow_up_prompts"]],
        fixture["candidate_messages"],
        strict=True,
    ):
        messages.extend([{"role": "user", "content": prompt}, deepcopy(response)])
    result = {
        "artifact_type": "synthetic_diagnostic",
        "origin": "synthetic_authored",
        "scenario_id": scenario["scenario_id"],
        "benchmark_version": "0.8",
        "benchmark_track": scenario["benchmark_track"],
        "language": "en",
        "system_prompt_digest": dep._sha256_text(system) if system is not None else None,
        "messages": messages,
    }
    if scenario["benchmark_track"] == "agentic":
        result["protocol"] = {
            "protocol_mode": scenario["protocol_mode"],
            "matched_pair_id": scenario["matched_pair_id"],
            "locale": scenario["locale"],
            "prefill_message_count": len(scenario.get("prefill_messages", [])),
        }
    return result


def _judge_messages(scenario: dict, transcript: dict) -> list[dict]:
    evidence = (
        dep._bound_agentic_transcript_evidence(scenario, transcript)
        if (scenario["benchmark_track"] == "agentic")
        else None
    )
    return dep._judge_request(scenario, transcript, evidence)


def _execution_status(tasks: list[dict]) -> str:
    if all(t["status"] == "complete" for t in tasks):
        return "complete"
    return "partial" if any(t["attempts"] for t in tasks) else "not_run"


def run_study(
    *, manifest_path: Path, output_root: Path, dry_run: bool = True, transport=None
) -> dict:
    inputs = _load_inputs(Path(manifest_path))
    plan = plan_study(
        inputs["manifest"], inputs["scenarios"], inputs["fixtures"], selection=inputs["selection"]
    )
    if dry_run:
        return {k: v for k, v in {**plan, "execution_status": "not_run"}.items() if k != "tasks"}
    root = Path(output_root).resolve()
    for path in inputs["paths"].values():
        if path and (root == path or path.is_relative_to(root) or root.is_relative_to(path)):
            raise ValidationError("study output must not overlap source inputs")
    if root.exists():
        checked = validate_study_state(root / "study.json", root)
        if _identity(inputs) != checked["input_digest"]:
            raise ValidationError("cannot resume: study inputs differ from frozen run")
    else:
        _initialize(inputs, root)
    inputs = _load_inputs(root / "study.json", confined=True)
    manifest = inputs["manifest"]
    state = read_json(root / "study-state.json")
    by_id = {row["scenario_id"]: row for row in inputs["scenarios"]}
    targets = {c["id"]: c for c in manifest["targets"]}
    judges = {c["id"]: c for c in manifest["judges"]}
    fixtures = {f["fixture_id"]: f for f in inputs["fixtures"]}
    task_map = {task["task_id"]: task for task in state["tasks"]}
    spent_requests = sum(len(a["requests"]) for t in state["tasks"] for a in t["attempts"])
    spent_tokens = sum(
        r["reserved_output_tokens"]
        for t in state["tasks"]
        for a in t["attempts"]
        for r in a["requests"]
    )
    for task in state["tasks"]:
        if task["status"] == "complete":
            continue
        if task["dependency"] and task_map[task["dependency"]]["status"] != "complete":
            continue
        scenario = by_id[task["scenario_id"]]
        config = (
            targets[task["target_id"]] if task["kind"] == "generation" else judges[task["judge_id"]]
        )
        directory = root / "tasks" / task["task_id"]
        directory.mkdir(parents=True, exist_ok=True)
        scenario_path = directory / "scenario.jsonl"
        dep._atomic_write_jsonl(scenario_path, [scenario])
        while len(task["attempts"]) < manifest["retry_attempts"]:
            attempt = {"attempt": len(task["attempts"]) + 1, "status": "running", "requests": []}
            task["attempts"].append(attempt)
            task["status"] = "error"
            attempt_dir = directory / f"attempt-{attempt['attempt']}"
            attempt_dir.mkdir(exist_ok=True)
            _write(root / "study-state.json", state)

            def send(
                url,
                payload,
                headers,
                timeout,
                *,
                config=config,
                attempt=attempt,
                attempt_dir=attempt_dir,
            ):
                nonlocal spent_requests, spent_tokens
                if payload.get(api.token_field(config)) != config["max_tokens"]:
                    raise ValidationError("request token cap does not match study configuration")
                if timeout != api.timeout_seconds(config):
                    raise ValidationError("request timeout does not match study configuration")
                if (
                    spent_requests + 1 > manifest["budget"]["max_requests"]
                    or spent_tokens + config["max_tokens"] > manifest["budget"]["max_output_tokens"]
                ):
                    raise ValidationError("execution budget exhausted")
                number = len(attempt["requests"]) + 1
                request_path = attempt_dir / f"request-{number}.json"
                _write(request_path, api.request_record(config, url, payload, headers=headers))
                request = {
                    "request": _artifact(root, request_path),
                    "response": None,
                    "reserved_output_tokens": config["max_tokens"],
                }
                attempt["requests"].append(request)
                spent_requests += 1
                spent_tokens += config["max_tokens"]
                _write(root / "study-state.json", state)
                try:
                    response = (transport or dep._post_json)(url, payload, headers, timeout)
                except Exception as exc:
                    request["error_type"] = type(exc).__name__
                    _write(root / "study-state.json", state)
                    raise
                response_path = attempt_dir / f"response-{number}.json"
                _write(response_path, response)
                request["response"] = _artifact(root, response_path)
                _write(root / "study-state.json", state)
                return response

            def send_generation(url, payload, headers, timeout, *, config=config, send=send):
                # run_scenarios uses chat internally; the ledger records only the
                # native request and packet, before adapting text at this boundary.
                native_payload = (
                    api.request_payload(config, payload["messages"])
                    if api.protocol(config) != "chat_completions"
                    else payload
                )
                response = send(
                    api.endpoint(config),
                    native_payload,
                    api.request_headers(config, headers),
                    timeout,
                )
                content = api.assistant_content(response, config)
                if api.protocol(config) == "chat_completions":
                    return response
                return {"choices": [{"message": {"content": content}}]}

            try:
                output = attempt_dir / "transcript.jsonl"
                if task["kind"] == "generation":
                    dep.run_scenarios(
                        scenarios_path=scenario_path,
                        target_base_url=config["base_url"],
                        target_model=config["model"],
                        candidate_digest=config["candidate_digest"],
                        output_path=output,
                        system_prompt_path=inputs["paths"]["system_prompt_path"],
                        target_api_key_env=config["api_key_env"],
                        temperature=config["temperature"],
                        max_tokens=config["max_tokens"],
                        transport=send_generation,
                        timeout=api.timeout_seconds(config),
                    )
                    task["artifacts"] = {"transcript": _artifact(root, output)}
                else:
                    if task["kind"] == "fixture_rating":
                        transcript = _fixture_transcript(
                            scenario, fixtures[task["fixture_id"]], inputs["system"]
                        )
                        dep._atomic_write_jsonl(output, [transcript])
                        transcript_ref = _artifact(root, output)
                    else:
                        transcript_ref = task_map[task["dependency"]]["artifacts"]["transcript"]
                        transcript = _read_jsonl(_checked_artifact(root, transcript_ref))[0]
                    payload = api.request_payload(
                        config, _judge_messages(scenario, transcript), judge=True
                    )
                    response = send(
                        api.endpoint(config),
                        payload,
                        api.request_headers(
                            config,
                            dep._headers(dep._api_key_from_environment(config["api_key_env"])),
                        ),
                        api.timeout_seconds(config),
                    )
                    judgment = dep._parse_judgment(
                        api.assistant_content(response, config), scenario
                    )
                    annotation = {
                        "benchmark_version": "0.8",
                        "benchmark_track": scenario["benchmark_track"],
                        "scenario_id": scenario["scenario_id"],
                        "language": "en",
                        "model": task["target_id"] or "synthetic_authored",
                        "rater_id": task["task_id"],
                        "judge_model": config["model"],
                        "automated": True,
                        "evidence_stage": "PREVIEW",
                        **judgment,
                    }
                    annotation_path = attempt_dir / "annotation.jsonl"
                    dep._atomic_write_jsonl(annotation_path, [annotation])
                    task["artifacts"] = {
                        "transcript": transcript_ref,
                        "annotation": _artifact(root, annotation_path),
                    }
                task["status"] = "complete"
                attempt["status"] = "complete"
            except (RuntimeError, ValueError, OSError) as exc:
                attempt["status"] = "error"
                attempt["error_type"] = type(exc).__name__
            _write(root / "study-state.json", state)
            if task["status"] == "complete":
                break
    checked = validate_study_state(root / "study.json", root)
    return {
        "execution_status": checked["execution_status"],
        "task_count": len(state["tasks"]),
        "requests": spent_requests,
        "reserved_output_tokens": spent_tokens,
        "evidence_stage": "PREVIEW",
        "human_review": "not_performed",
        "deployment_action": "HOLD",
        "manifest": str(root / "study.json"),
        "state": str(root / "study-state.json"),
    }


def _validate_request_sequence(task, scenario, observed, inputs, root, completed, fixtures, config):
    if not observed:
        return
    if task["kind"] == "generation":
        messages = (
            [{"role": "system", "content": inputs["system"]}]
            if inputs["system"] is not None
            else []
        )
        messages.extend(deepcopy(scenario.get("prefill_messages", [])))
        prompts = [scenario["initial_prompt"], *scenario["follow_up_prompts"]]
        for index, (request, response) in enumerate(observed):
            messages.append({"role": "user", "content": prompts[index]})
            if api.canonical_messages(config, request["payload"]) != messages:
                raise ValidationError("captured request input differs from planned source prompt")
            try:
                content = api.assistant_content(response, config) if response is not None else None
            except RuntimeError:
                content = None
            if content is None:
                if index + 1 != len(observed):
                    raise ValidationError("requests continue after a missing or invalid response")
            else:
                messages.append({"role": "assistant", "content": content})
    else:
        if task["kind"] == "rating":
            if task["dependency"] not in completed:
                raise ValidationError("judge request lacks its completed source transcript")
            transcript = _read_jsonl(_checked_artifact(root, completed[task["dependency"]]))[0]
        else:
            transcript = _fixture_transcript(
                scenario, fixtures[task["fixture_id"]], inputs["system"]
            )
        expected = _judge_messages(scenario, transcript)
        if any(
            api.canonical_messages(config, request["payload"]) != expected
            for request, _ in observed
        ):
            raise ValidationError("captured judge input differs from frozen scoring prompt")


def validate_study_state(manifest_path: Path, run_root: Path) -> dict:
    try:
        return _validate_study_state(manifest_path, run_root)
    except (KeyError, TypeError, AttributeError, IndexError, RuntimeError) as exc:
        raise ValidationError(f"malformed study evidence: {type(exc).__name__}") from exc


def _validate_study_state(manifest_path: Path, run_root: Path) -> dict:
    root = Path(run_root).resolve()
    path = Path(manifest_path).resolve()
    if path != root / "study.json":
        raise ValidationError("verification requires the frozen study.json inside run root")
    inputs = _load_inputs(path, confined=True)
    manifest = inputs["manifest"]
    plan = plan_study(
        manifest, inputs["scenarios"], inputs["fixtures"], selection=inputs["selection"]
    )
    state = read_json(root / "study-state.json")
    if state.get("instrument") != _instrument():
        raise ValidationError("study instrument changed; use the pinned runtime or a new study")
    if state.get("manifest_digest") != record_digest(manifest) or state.get(
        "input_digest"
    ) != _identity(inputs):
        raise ValidationError("study input or manifest digest mismatch")
    tasks = state.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != len(plan["tasks"]):
        raise ValidationError("study task matrix is incomplete")
    by_id = {row["scenario_id"]: row for row in inputs["scenarios"]}
    fixtures = {f["fixture_id"]: f for f in inputs["fixtures"]}
    targets = {c["id"]: c for c in manifest["targets"]}
    judges = {c["id"]: c for c in manifest["judges"]}
    completed_transcripts = {}
    rows = []
    requests = tokens = 0
    for expected, task in zip(plan["tasks"], tasks, strict=True):
        if not isinstance(task, dict) or {k: task.get(k) for k in expected} != expected:
            raise ValidationError("study task matrix or provenance does not match manifest")
        if set(task) != set(expected) | {"status", "attempts", "artifacts"}:
            raise ValidationError("unexpected task fields")
        if task["status"] not in {"pending", "complete", "error"}:
            raise ValidationError("invalid task status")
        attempts = task["attempts"]
        if not isinstance(attempts, list) or len(attempts) > manifest["retry_attempts"]:
            raise ValidationError("invalid attempt count")
        if task["status"] == "pending" and (attempts or task["artifacts"]):
            raise ValidationError("pending task cannot contain completed evidence")
        if task["status"] == "error" and (not attempts or task["artifacts"]):
            raise ValidationError("failed task must retain attempts without completed artifacts")
        scenario = by_id[task["scenario_id"]]
        config = (
            targets[task["target_id"]] if task["kind"] == "generation" else judges[task["judge_id"]]
        )
        successful = []
        for number, attempt in enumerate(attempts, 1):
            if attempt.get("attempt") != number or attempt.get("status") not in {
                "complete",
                "error",
                "running",
            }:
                raise ValidationError("invalid attempt ledger")
            captures = attempt.get("requests")
            maximum = 1 + len(scenario["follow_up_prompts"]) if task["kind"] == "generation" else 1
            if not isinstance(captures, list) or len(captures) > maximum:
                raise ValidationError("request count exceeds task contract")
            observed = []
            for capture in captures:
                request = read_json(_checked_artifact(root, capture["request"]))
                payload = request["payload"]
                if (
                    request["url"] != api.endpoint(config)
                    or payload.get("model") != config["model"]
                ):
                    raise ValidationError("captured request model/endpoint does not match manifest")
                if (
                    payload.get(api.token_field(config)) != config["max_tokens"]
                    or capture.get("reserved_output_tokens") != config["max_tokens"]
                ):
                    raise ValidationError("captured token cap does not match manifest")
                actual_temp = payload.get("temperature")
                if actual_temp != config["temperature"]:
                    raise ValidationError("captured sampling settings do not match manifest")
                expected_payload = api.request_payload(
                    config,
                    api.canonical_messages(config, payload),
                    judge=task["kind"] != "generation",
                )
                if payload != expected_payload:
                    raise ValidationError("captured request has unregistered model settings")
                if request != api.request_record(config, api.endpoint(config), expected_payload):
                    raise ValidationError(
                        "captured protocol/timeout/headers does not match manifest"
                    )
                requests += 1
                tokens += capture["reserved_output_tokens"]
                response = (
                    read_json(_checked_artifact(root, capture["response"]))
                    if capture.get("response")
                    else None
                )
                observed.append((request, response))
            _validate_request_sequence(
                task, scenario, observed, inputs, root, completed_transcripts, fixtures, config
            )
            if attempt["status"] == "complete":
                if len(captures) != maximum or any(response is None for _, response in observed):
                    raise ValidationError("completed attempt lacks provider responses")
                successful.append(observed)
        if task["status"] != "complete":
            if successful:
                raise ValidationError("successful attempt conflicts with task state")
            continue
        if len(successful) != 1 or attempts[-1]["status"] != "complete":
            raise ValidationError("complete task must end with one successful attempt")
        observed = successful[0]
        transcript_path = _checked_artifact(root, task["artifacts"]["transcript"])
        transcript_rows = _read_jsonl(transcript_path)
        if len(transcript_rows) != 1:
            raise ValidationError("task transcript must contain exactly one scenario")
        transcript = transcript_rows[0]
        if (
            transcript.get("scenario_id") != scenario["scenario_id"]
            or transcript.get("benchmark_version") != "0.8"
            or transcript.get("benchmark_track") != scenario["benchmark_track"]
            or transcript.get("language") != "en"
        ):
            raise ValidationError("transcript scope does not match scenario")
        if task["kind"] == "generation":
            generation_settings = {"max_tokens": config["max_tokens"]}
            if config["temperature"] is not None:
                generation_settings["temperature"] = config["temperature"]
            system_digest = (
                dep._sha256_text(inputs["system"]) if inputs["system"] is not None else None
            )
            scenario_path = root / "tasks" / task["task_id"] / "scenario.jsonl"
            if _read_jsonl(scenario_path) != [scenario]:
                raise ValidationError("generation source artifact differs from frozen scenario")
            _, dataset_digest = dep.load_scenario_source(scenario_path)
            if (
                transcript.get("system_prompt_digest") != system_digest
                or transcript.get("generation_settings") != generation_settings
                or transcript.get("artifact_type") != "target_transcript"
                or transcript.get("dataset_digest") != dataset_digest
            ):
                raise ValidationError("transcript configuration provenance mismatch")
            messages = (
                [{"role": "system", "content": inputs["system"]}]
                if inputs["system"] is not None
                else []
            )
            messages.extend(deepcopy(scenario.get("prefill_messages", [])))
            for prompt, (request, response) in zip(
                [scenario["initial_prompt"], *scenario["follow_up_prompts"]], observed, strict=True
            ):
                messages.append({"role": "user", "content": prompt})
                if api.canonical_messages(config, request["payload"]) != messages:
                    raise ValidationError("raw generation input differs from source transcript")
                messages.append(
                    {"role": "assistant", "content": api.assistant_content(response, config)}
                )
            if (
                transcript["messages"] != messages
                or transcript.get("candidate_digest") != config["candidate_digest"]
                or transcript.get("target_model") != config["model"]
            ):
                raise ValidationError("raw generation response differs from transcript")
            completed_transcripts[task["task_id"]] = task["artifacts"]["transcript"]
            continue
        if task["kind"] == "rating":
            if completed_transcripts.get(task["dependency"]) != task["artifacts"]["transcript"]:
                raise ValidationError("rating does not reference its generated transcript")
        elif transcript != _fixture_transcript(
            scenario, fixtures[task["fixture_id"]], inputs["system"]
        ):
            raise ValidationError("synthetic diagnostic transcript does not match authored fixture")
        request, response = observed[0]
        if api.canonical_messages(config, request["payload"]) != _judge_messages(
            scenario, transcript
        ):
            raise ValidationError("raw judge input differs from scenario/transcript evidence")
        judgment = dep._parse_judgment(api.assistant_content(response, config), scenario)
        annotations = _read_jsonl(_checked_artifact(root, task["artifacts"]["annotation"]))
        if len(annotations) != 1:
            raise ValidationError("task requires exactly one annotation")
        annotation = annotations[0]
        if any(annotation.get(k) != v for k, v in judgment.items()):
            raise ValidationError("annotation differs from raw judge response")
        if (
            annotation.get("scenario_id") != scenario["scenario_id"]
            or annotation.get("rater_id") != task["task_id"]
        ):
            raise ValidationError("annotation identity mismatch")
        expected_annotation = {
            "benchmark_version": "0.8",
            "benchmark_track": scenario["benchmark_track"],
            "scenario_id": scenario["scenario_id"],
            "language": "en",
            "model": task["target_id"] or "synthetic_authored",
            "rater_id": task["task_id"],
            "judge_model": config["model"],
            "automated": True,
            "evidence_stage": "PREVIEW",
            **judgment,
        }
        if annotation != expected_annotation:
            raise ValidationError("annotation configuration provenance mismatch")
        rows.append(
            {**expected, "transcript_digest": task["artifacts"]["transcript"]["sha256"], **judgment}
        )
    if (
        requests > manifest["budget"]["max_requests"]
        or tokens > manifest["budget"]["max_output_tokens"]
    ):
        raise ValidationError("recorded execution exceeds declared budget")
    return {
        "manifest": manifest,
        "tasks": tasks,
        "scenarios": inputs["scenarios"],
        "fixtures": inputs["fixtures"],
        "execution_status": _execution_status(tasks),
        "rows": rows,
        "input_digest": state["input_digest"],
        "requests": requests,
        "reserved_output_tokens": tokens,
    }
