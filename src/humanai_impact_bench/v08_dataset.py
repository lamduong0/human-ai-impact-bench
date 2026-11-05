"""Deterministic English-only migration and pilot selection for v0.8."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from humanai_impact_bench.constants import V07_CATEGORIES, V07_CORE_CATEGORIES
from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.validation import ValidationError, load_scenarios

SELECTION_SEED = "humanai-v08-pilot-v1"
TRACKS = ("core", "agentic")
SPLITS = ("calibration", "public_evaluation")


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValidationError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{path} must be an object")
    return value


def single_tag(record: dict, prefix: str) -> str:
    values = [t[len(prefix) :] for t in record["tags"] if t.startswith(prefix)]
    if len(values) != 1 or not values[0]:
        raise ValidationError(f"{record['scenario_id']} requires exactly one {prefix} tag")
    return values[0]


def scenario_set_digest(records: list[dict]) -> str:
    payload = json.dumps(
        sorted(records, key=lambda r: r["scenario_id"]),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return _sha(payload)


def _family_key(row: dict) -> str:
    return "|".join((row["benchmark_track"], row["category"], single_tag(row, "concept-family-")))


def _validate_pairs(records: list[dict]) -> None:
    pairs: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        if row["benchmark_track"] == "agentic":
            pairs[row["matched_pair_id"]].append(row)
    for pair_id, members in pairs.items():
        if len(members) != 2 or {r["protocol_mode"] for r in members} != {
            "control",
            "prefill_stress",
        }:
            raise ValidationError(f"incomplete or duplicate agentic pair {pair_id}")
        comparable = []
        for row in members:
            copy = {
                k: v
                for k, v in row.items()
                if k not in {"scenario_id", "protocol_mode", "prefill_messages", "tags"}
            }
            copy["tags"] = sorted(t for t in row["tags"] if not t.startswith("protocol-"))
            comparable.append(copy)
        if comparable[0] != comparable[1]:
            raise ValidationError(f"agentic pair {pair_id} has mismatched shared content")


def load_v08_records(root: Path, track: str | None = None) -> list[dict]:
    """Load exact English category directories, rejecting mixed or duplicate rows."""
    if track is not None and track not in TRACKS:
        raise ValidationError("track must be core or agentic")
    rows = []
    for current in TRACKS if track is None else (track,):
        paths = sorted((Path(root) / current / "en").glob("*.jsonl"))
        if not paths:
            raise ValidationError(f"no v0.8 {current} English scenarios in {root}")
        for path in paths:
            loaded = load_scenarios(path)
            if any(
                r["benchmark_version"] != "0.8"
                or r["benchmark_track"] != current
                or r["language"] != "en"
                or r["category"] != path.stem
                for r in loaded
            ):
                raise ValidationError(f"scenario scope does not match {path}")
            rows.extend(loaded)
    if len({r["scenario_id"] for r in rows}) != len(rows):
        raise ValidationError("duplicate v0.8 scenario identity")
    _validate_pairs(rows)
    return sorted(rows, key=lambda r: r["scenario_id"])


def select_pilot(records: list[dict], assignments: dict[str, str]) -> list[str]:
    """Select two families per category, preserving complete agentic pairs."""
    if len({r["scenario_id"] for r in records}) != len(records):
        raise ValidationError("duplicate scenario identity in pilot input")
    _validate_pairs(records)
    groups: dict[tuple[str, str, str], dict[str, dict[str, list[str]]]] = {}
    categories: dict[str, set[str]] = defaultdict(set)
    for row in records:
        track = row["benchmark_track"]
        family = single_tag(row, "concept-family-")
        context = single_tag(row, "context-")
        split = assignments.get(_family_key(row))
        if split not in SPLITS:
            raise ValidationError(f"missing or invalid split assignment for {_family_key(row)}")
        categories[track].add(row["category"])
        families = groups.setdefault((track, row["category"], split), {})
        families.setdefault(family, {}).setdefault(context, []).append(row["scenario_id"])
    expected = {"core": V07_CORE_CATEGORIES, "agentic": V07_CATEGORIES}
    if categories != expected:
        raise ValidationError("pilot must cover every core and agentic category")
    selected = []
    for track in TRACKS:
        for category in sorted(categories[track]):
            for split in SPLITS:
                families = groups.get((track, category, split), {})
                if not families:
                    raise ValidationError(f"missing {split} families in {track}/{category}")
                prefix = f"{SELECTION_SEED}|{track}|{category}|{split}|"
                family = min(families, key=lambda name: (_sha((prefix + name).encode()), name))
                contexts = families[family]
                context = min(
                    contexts, key=lambda name: (_sha((prefix + family + "|" + name).encode()), name)
                )
                ids = contexts[context]
                if len(ids) != (2 if track == "agentic" else 1):
                    raise ValidationError("pilot context has unexpected record/pair count")
                selected.extend(ids)
    return sorted(selected)


def _version_id(value: str) -> str:
    if not value.startswith("v07-"):
        raise ValidationError(f"unexpected source identifier prefix: {value}")
    return "v08-" + value[4:]


def _atomic_write(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".v08-")
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(contents)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prepare_v08(source_root: Path, output_root: Path) -> dict[str, object]:
    """Prepare the complete draft corpus without mutating source or conflicting output."""
    source = Path(source_root).resolve()
    output = Path(output_root).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValidationError("source and output directories overlap")
    source_index = _read_json(source / "configuration-index.json")
    split_index = _read_json(source / "split-index.json")
    if (
        source_index.get("benchmark_version") != "0.7"
        or split_index.get("benchmark_version") != "0.7"
    ):
        raise ValidationError("source indexes must describe v0.7")
    source_splits = {}
    for item in split_index.get("items", []):
        if item["language"] == "en":
            if item["scenario_id"] in source_splits:
                raise ValidationError("duplicate source split identity")
            source_splits[item["scenario_id"]] = item
    files: dict[str, bytes] = {}
    records: list[dict] = []
    lineage: dict[str, dict] = {}
    assignments: dict[str, str] = {}
    configuration_summaries = {}
    changes = []
    for track in TRACKS:
        source_summary = source_index["configurations"][f"v0.7-{track}-en"]
        rows = []
        data_files = []
        expected_paths = {f["path"] for f in source_summary["files"]}
        actual_paths = {str(p.relative_to(source)) for p in (source / track / "en").glob("*.jsonl")}
        if expected_paths != actual_paths:
            raise ValidationError(f"source {track} file inventory does not match configuration")
        for file in source_summary["files"]:
            relative = Path(file["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValidationError("source configuration path must stay inside source root")
            path = source / relative
            if not path.resolve().is_relative_to(source):
                raise ValidationError("source file symlink escapes source root")
            if _sha(path.read_bytes()) != file["sha256"]:
                raise ValidationError(f"source file digest mismatch: {relative}")
            migrated = []
            for old in load_scenarios(path):
                if (
                    old["benchmark_version"] != "0.7"
                    or old["language"] != "en"
                    or old["benchmark_track"] != track
                ):
                    raise ValidationError("source record has incompatible version/track/language")
                new = deepcopy(old)
                new["benchmark_version"] = "0.8"
                new["scenario_id"] = _version_id(old["scenario_id"])
                changed = ["benchmark_version", "scenario_id"]
                if "matched_pair_id" in new:
                    new["matched_pair_id"] = _version_id(old["matched_pair_id"])
                    changed.append("matched_pair_id")
                source_split = source_splits.get(old["scenario_id"])
                family = single_tag(new, "concept-family-")
                context = single_tag(new, "context-")
                if source_split is None or any(
                    source_split[k] != v
                    for k, v in {
                        "benchmark_track": track,
                        "category": new["category"],
                        "concept_family_id": family,
                        "context_id": context,
                    }.items()
                ):
                    raise ValidationError("source split lineage is missing or inconsistent")
                key = _family_key(new)
                if key in assignments and assignments[key] != source_split["split"]:
                    raise ValidationError("source family crosses split assignments")
                assignments[key] = source_split["split"]
                if new["scenario_id"] in lineage:
                    raise ValidationError("duplicate migrated scenario identity")
                lineage[new["scenario_id"]] = {
                    "source_version": "0.7",
                    "source_scenario_id": old["scenario_id"],
                    "source_path": os.path.relpath(path, output),
                    "source_digest": record_digest(old),
                    "scenario_digest": record_digest(new),
                    "changed_fields": sorted(changed),
                }
                changes.append(
                    {
                        "scenario_id": new["scenario_id"],
                        "reason": "versioned_migration",
                        "old_digest": record_digest(old),
                        "new_digest": record_digest(new),
                        "changed_fields": sorted(changed),
                        "audit_finding_id": None,
                    }
                )
                migrated.append(new)
            blob = (
                "".join(
                    json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n"
                    for r in migrated
                )
            ).encode()
            files[str(relative)] = blob
            data_files.append(
                {"path": str(relative), "sha256": _sha(blob), "scenario_count": len(migrated)}
            )
            rows.extend(migrated)
        expected_count = 2400 if track == "core" else 400
        if len(rows) != expected_count or {r["category"] for r in rows} != (
            V07_CORE_CATEGORIES if track == "core" else V07_CATEGORIES
        ):
            raise ValidationError(f"source {track} corpus coverage differs from approved baseline")
        review = {
            "manifest_version": "0.3",
            "benchmark_version": "0.8",
            "benchmark_track": track,
            "language": "en",
            "scenario_count": len(rows),
            "allowed_statuses": ["draft_unreviewed"],
            "items": {
                r["scenario_id"]: {
                    "scenario_digest": record_digest(r),
                    "status": "draft_unreviewed",
                    "review_events": [],
                }
                for r in rows
            },
        }
        review_path = f"{track}/en/review-status.json"
        files[review_path] = _json_bytes(review)
        configuration_summaries[f"v0.8-{track}-en"] = {
            "benchmark_track": track,
            "language": "en",
            "scenario_count": len(rows),
            "scenario_digest": scenario_set_digest(rows),
            "category_counts": dict(sorted(Counter(r["category"] for r in rows).items())),
            "files": data_files,
            "review_manifest": {"path": review_path, "sha256": _sha(files[review_path])},
        }
        records.extend(rows)
    if set(source_splits) != {v["source_scenario_id"] for v in lineage.values()}:
        raise ValidationError("source split inventory does not match English source records")
    pilot_ids = set(select_pilot(records, assignments))
    pilot_records = []
    for row in sorted(records, key=lambda r: r["scenario_id"]):
        if row["scenario_id"] in pilot_ids:
            item = {
                "scenario_id": row["scenario_id"],
                "track": row["benchmark_track"],
                "category": row["category"],
                "family_id": single_tag(row, "concept-family-"),
                "context_id": single_tag(row, "context-"),
                "split": assignments[_family_key(row)],
                "scenario_digest": record_digest(row),
            }
            if "matched_pair_id" in row:
                item["matched_pair_id"] = row["matched_pair_id"]
            pilot_records.append(item)
    common = {"index_version": "0.1", "benchmark_version": "0.8", "language": "en"}
    files["lineage-index.json"] = _json_bytes(
        {**common, "scenario_count": len(records), "entries": lineage}
    )
    files["split-index.json"] = _json_bytes(
        {
            **common,
            "assignments": assignments,
            "source_index_digest": _sha((source / "split-index.json").read_bytes()),
        }
    )
    files["pilot-index.json"] = _json_bytes(
        {
            **common,
            "selection_seed": SELECTION_SEED,
            "scenario_count": len(pilot_records),
            "records": pilot_records,
        }
    )
    files["change-ledger.json"] = _json_bytes({**common, "changes": changes})
    files["audit-ledger.json"] = _json_bytes(
        {**common, "semantic_audit_status": "not_run", "findings": []}
    )
    index = {
        **common,
        "configuration_count": 2,
        "scenario_count": len(records),
        "review_status_counts": {"draft_unreviewed": len(records)},
        "evidence_stage": "PREVIEW",
        "deployment_action": "HOLD",
        "configurations": configuration_summaries,
        "artifacts": {
            Path(name).stem: {"path": name, "sha256": _sha(blob)}
            for name, blob in files.items()
            if "/" not in name
        },
    }
    files["configuration-index.json"] = _json_bytes(index)
    if output.exists():
        existing = {str(p.relative_to(output)): p for p in output.rglob("*") if p.is_file()}
        if any(p.is_symlink() for p in output.rglob("*")):
            raise ValidationError("existing output contains a symlink")
        if existing and (
            set(existing) != set(files)
            or any(existing[n].read_bytes() != b for n, b in files.items())
        ):
            raise ValidationError("existing output conflicts with deterministic preparation")
    for name, blob in files.items():
        _atomic_write(output / name, blob)
    return index


def materialize_selection(root: Path, selection: Path, track: str, output: Path) -> dict:
    """Write one selected track after validating all identities and source digests."""
    if track not in TRACKS:
        raise ValidationError("track must be core or agentic")
    if Path(output).resolve().is_relative_to(Path(root).resolve()):
        raise ValidationError("materialized output must stay outside the frozen corpus")
    rows = {r["scenario_id"]: r for r in load_v08_records(root)}
    assignments = _read_json(Path(root) / "split-index.json")["assignments"]
    index = _read_json(selection)
    entries = index.get("records")
    if index.get("benchmark_version") != "0.8" or not isinstance(entries, list) or not entries:
        raise ValidationError("invalid v0.8 selection index")
    selected = []
    seen = set()
    for entry in entries:
        identity = entry["scenario_id"]
        if identity in seen or identity not in rows:
            raise ValidationError("duplicate or unknown selected identity")
        seen.add(identity)
        row = rows[identity]
        if entry["scenario_digest"] != record_digest(row):
            raise ValidationError(f"selection source digest mismatch: {identity}")
        if entry["track"] != row["benchmark_track"]:
            raise ValidationError("selection track does not match scenario")
        if entry.get("split") != assignments.get(_family_key(row)):
            raise ValidationError("selection split does not match inherited family assignment")
        expected_metadata = {
            "category": row["category"],
            "family_id": single_tag(row, "concept-family-"),
            "context_id": single_tag(row, "context-"),
        }
        if any(entry.get(key) != value for key, value in expected_metadata.items()):
            raise ValidationError("selection metadata does not match source scenario")
        if entry.get("matched_pair_id") != row.get("matched_pair_id"):
            raise ValidationError("selection matched pair does not match source scenario")
        if entry["track"] == track:
            selected.append(row)
    if not selected:
        raise ValidationError("selection has no records in the requested track")
    _validate_pairs(selected)
    _atomic_write(
        Path(output), ("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in selected)).encode()
    )
    return {
        "benchmark_version": "0.8",
        "benchmark_track": track,
        "language": "en",
        "scenario_count": len(selected),
        "scenario_digest": scenario_set_digest(selected),
    }
