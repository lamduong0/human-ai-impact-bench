"""Deterministic lineage, split, and configuration artifacts for v0.7."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from humanai_impact_bench.digests import record_digest
from humanai_impact_bench.review import validate_v07_review_manifest
from humanai_impact_bench.validation import ValidationError, load_scenarios

ROOT = Path(__file__).resolve().parents[1]
V07_ROOT = ROOT / "data" / "scenarios" / "v0.7"
TRACKS = ("core", "agentic")
LANGUAGES = ("en", "vi")
CONFIGURATION_NAMES = {
    ("core", "en"): "v0.7-core-en",
    ("core", "vi"): "v0.7-core-vi-preview",
    ("agentic", "en"): "v0.7-agentic-en",
    ("agentic", "vi"): "v0.7-agentic-vi-preview",
}
SELECTION_RULE = (
    "Within each track/category, sort the 25 concept-family IDs. Assign the first 20 "
    "families to `calibration` and the final 5 to `public_evaluation`. Every context, "
    "mode, and language record for a family inherits that assignment."
)
_SOURCE_VERSION_PATTERN = re.compile(r"v(\d+)-(\d+)")


def scenario_set_digest(records: list[dict[str, Any]]) -> str:
    """Return a canonical digest for a configuration's exact scenario set."""
    ordered = sorted(
        records,
        key=lambda record: (
            record["language"],
            record["category"],
            record["scenario_id"],
        ),
    )
    payload = json.dumps(
        ordered,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def single_tag(record: dict[str, Any], prefix: str) -> str:
    """Return the value of exactly one non-empty tag with ``prefix``."""
    tags = record.get("tags")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ValidationError(f"{record.get('scenario_id', '<unknown>')} tags must be strings")
    values = [tag.removeprefix(prefix) for tag in tags if tag.startswith(prefix)]
    if len(values) != 1 or not values[0]:
        label = prefix.rstrip("-")
        raise ValidationError(
            f"{record.get('scenario_id', '<unknown>')} must have exactly one non-empty {label} tag"
        )
    return values[0]


def load_v07_configuration(
    track: str,
    language: str,
    root: Path = V07_ROOT,
) -> list[dict[str, Any]]:
    """Load one v0.7 track/language configuration in deterministic file order."""
    if track not in TRACKS:
        raise ValidationError("track must be 'core' or 'agentic'")
    if language not in LANGUAGES:
        raise ValidationError("language must be 'en' or 'vi'")
    source_dir = Path(root) / track / language
    paths = sorted(source_dir.glob("*.jsonl"))
    if not paths:
        raise ValidationError(f"no JSONL scenario files found in {source_dir}")

    records: list[dict[str, Any]] = []
    for path in paths:
        file_records = load_scenarios(path)
        if {record["category"] for record in file_records} != {path.stem}:
            raise ValidationError(f"{path} must contain only category {path.stem!r}")
        records.extend(file_records)

    if {record["benchmark_version"] for record in records} != {"0.7"}:
        raise ValidationError(f"{source_dir} must contain only v0.7 scenarios")
    if {record["benchmark_track"] for record in records} != {track}:
        raise ValidationError(f"{source_dir} benchmark track does not match its directory")
    if {record["language"] for record in records} != {language}:
        raise ValidationError(f"{source_dir} language does not match its directory")
    identities = [record["scenario_id"] for record in records]
    if len(identities) != len(set(identities)):
        raise ValidationError(f"{source_dir} contains duplicate scenario IDs")
    return records


def _configurations(root: Path) -> list[tuple[str, str, list[dict[str, Any]]]]:
    return [
        (track, language, load_v07_configuration(track, language, root))
        for track in TRACKS
        for language in LANGUAGES
    ]


def _source_version(record: dict[str, Any]) -> str:
    value = single_tag(record, "source-version-")
    match = _SOURCE_VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise ValidationError(f"{record['scenario_id']} has invalid source-version tag")
    version = ".".join(match.groups())
    if version == "0.7":
        if (
            record.get("benchmark_version") != "0.7"
            or record.get("language") != "vi"
            or record.get("benchmark_track") not in TRACKS
        ):
            raise ValidationError("v0.7 source requires a v0.7 Vietnamese target")
        if single_tag(record, "source-language-") != "en":
            raise ValidationError("v0.7 translation source-language must be en")
    elif version not in {"0.5", "0.6"}:
        raise ValidationError(f"{record['scenario_id']} source version must be 0.5 or 0.6")
    elif any(tag.startswith("source-language-") for tag in record["tags"]):
        raise ValidationError("source-language is reserved for v0.7 EN-to-VI translation")
    return version


def _find_source(
    root: Path,
    version: str,
    language: str,
    scenario_id: str,
    *,
    track: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    if version == "0.7":
        if track not in TRACKS or language != "en":
            raise ValidationError("v0.7 source resolution requires a track and English language")
        version_dir = root / track / language
    else:
        version_dir = root.parent / f"v{version}"
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(version_dir.rglob("*.jsonl")):
        for record in load_scenarios(path):
            if record["scenario_id"] == scenario_id and record["language"] == language:
                matches.append((path, record))
    if len(matches) != 1:
        raise ValidationError(
            f"source v{version}:{language}:{scenario_id} must resolve to exactly one record"
        )
    path, record = matches[0]
    if record["benchmark_version"] != version:
        raise ValidationError(
            f"source {scenario_id} benchmark_version {record['benchmark_version']!r} "
            f"does not match tagged version {version!r}"
        )
    if version == "0.7" and record.get("benchmark_track") != track:
        raise ValidationError(f"source {scenario_id} benchmark_track does not match {track!r}")
    return path, record


def _lineage_tags(record: dict[str, Any]) -> tuple[str, str, str, str | None, str | None]:
    concept_family_id = single_tag(record, "concept-family-")
    context_id = single_tag(record, "context-")
    derivation = single_tag(record, "derivation-")
    if derivation not in {"adapted", "authored-new"}:
        raise ValidationError(f"{record['scenario_id']} has unsupported derivation {derivation!r}")

    if derivation == "adapted":
        return (
            concept_family_id,
            context_id,
            derivation,
            _source_version(record),
            single_tag(record, "source-scenario-"),
        )
    if any(
        tag.startswith(("source-version-", "source-scenario-", "source-language-"))
        for tag in record["tags"]
    ):
        raise ValidationError(
            f"{record['scenario_id']} authored-new record must not claim a source"
        )
    return concept_family_id, context_id, derivation, None, None


def _lineage_item(root: Path, track: str, language: str, record: dict[str, Any]) -> dict[str, Any]:
    concept_family_id, context_id, derivation, version, source_scenario_id = _lineage_tags(record)
    source: dict[str, Any] | None = None
    if derivation == "adapted":
        assert version is not None and source_scenario_id is not None
        if version == "0.7" and (
            record["benchmark_track"] != track or record["language"] != language
        ):
            raise ValidationError("translation target track/language does not match configuration")
        source_path, source_record = _find_source(
            root,
            version,
            "en" if version == "0.7" else language,
            source_scenario_id,
            track=track if version == "0.7" else None,
        )
        if version == "0.7":
            # Intra-version edges are VI -> EN only. Validating the EN source's
            # tags rules out a back edge (and hence self/cyclic ancestry) without
            # conflating identical scenario IDs in different language records.
            _lineage_tags(source_record)
        source = {
            "benchmark_version": version,
            "language": source_record["language"],
            "path": str(source_path.relative_to(root.parent)),
            "scenario_id": source_record["scenario_id"],
            "scenario_sha256": record_digest(source_record),
        }
        if version == "0.7":
            source["benchmark_track"] = track
    return {
        "concept_family_id": concept_family_id,
        "context_id": context_id,
        "derivation": derivation.replace("-", "_"),
        "source": source,
        "target": {
            "benchmark_track": track,
            "category": record["category"],
            "language": language,
            "scenario_id": record["scenario_id"],
            "scenario_sha256": record_digest(record),
        },
    }


def build_lineage_index(root: Path = V07_ROOT) -> dict[str, Any]:
    """Build immutable source/target lineage for every v0.7 scenario."""
    root = Path(root)
    items = [
        _lineage_item(root, track, language, record)
        for track, language, records in _configurations(root)
        for record in records
    ]
    target_identities = [
        (
            item["target"]["benchmark_track"],
            item["target"]["language"],
            item["target"]["scenario_id"],
        )
        for item in items
    ]
    if len(target_identities) != len(set(target_identities)):
        raise ValidationError("v0.7 lineage contains duplicate target identities")
    items.sort(
        key=lambda item: (
            item["target"]["benchmark_track"],
            item["target"]["language"],
            item["target"]["category"],
            item["target"]["scenario_id"],
        )
    )
    return {
        "index_version": "0.1",
        "benchmark_version": "0.7",
        "scenario_count": len(items),
        "derivation_counts": dict(sorted(Counter(item["derivation"] for item in items).items())),
        "items": items,
    }


def build_split_index(root: Path = V07_ROOT) -> dict[str, Any]:
    """Assign every concept family to a deterministic public split."""
    records = [
        (track, language, record, *_lineage_tags(record)[:2])
        for track, language, configuration in _configurations(Path(root))
        for record in configuration
    ]
    families: dict[tuple[str, str], set[str]] = defaultdict(set)
    for track, _language, record, family, _context in records:
        families[(track, record["category"])].add(family)

    assignments: dict[tuple[str, str, str], str] = {}
    for (track, category), category_families in sorted(families.items()):
        ordered = sorted(category_families)
        if len(ordered) != 25:
            raise ValidationError(
                f"{track}/{category} must have exactly 25 concept families; found {len(ordered)}"
            )
        for index, family in enumerate(ordered):
            assignments[(track, category, family)] = (
                "calibration" if index < 20 else "public_evaluation"
            )

    items = []
    for track, language, record, family, context in records:
        items.append(
            {
                "benchmark_track": track,
                "category": record["category"],
                "concept_family_id": family,
                "context_id": context,
                "language": language,
                "scenario_id": record["scenario_id"],
                "split": assignments[(track, record["category"], family)],
            }
        )
    items.sort(
        key=lambda item: (
            item["benchmark_track"],
            item["language"],
            item["category"],
            item["scenario_id"],
        )
    )
    return {
        "index_version": "0.1",
        "benchmark_version": "0.7",
        "selection_rule": SELECTION_RULE,
        "scenario_count": len(items),
        "split_counts": dict(sorted(Counter(item["split"] for item in items).items())),
        "items": items,
    }


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_required_json(root: Path, name: str) -> tuple[Path, dict[str, Any]]:
    path = root / name
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"required artifact is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"required artifact is invalid: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"required artifact must be a JSON object: {path}")
    return path, value


def _validate_overlap_audit(
    overlap: dict[str, Any],
    configurations: list[tuple[str, str, list[dict[str, Any]]]],
) -> None:
    required = {
        "audit_version",
        "benchmark_version",
        "candidate_count",
        "candidates",
        "configuration_sha256",
        "resolutions",
        "scenario_count",
        "valid",
    }
    missing = sorted(required - set(overlap))
    if missing:
        raise ValidationError(f"overlap audit is missing required fields: {', '.join(missing)}")
    if (
        overlap["audit_version"] != "0.1"
        or overlap["benchmark_version"] != "0.7"
        or not isinstance(overlap["candidates"], list)
        or not isinstance(overlap["resolutions"], list)
        or not isinstance(overlap["candidate_count"], int)
        or isinstance(overlap["candidate_count"], bool)
        or overlap["candidate_count"] != len(overlap["candidates"])
        or overlap["candidate_count"] != len(overlap["resolutions"])
        or overlap["valid"] is not True
    ):
        raise ValidationError("overlap audit has an invalid v0.7 contract")

    expected_count = sum(len(records) for _track, _language, records in configurations)
    expected_digests = {
        CONFIGURATION_NAMES[(track, language)]: scenario_set_digest(records)
        for track, language, records in configurations
    }
    if (
        overlap["scenario_count"] != expected_count
        or overlap["configuration_sha256"] != expected_digests
    ):
        raise ValidationError("overlap audit does not match current scenarios")


def build_configuration_index(root: Path = V07_ROOT) -> dict[str, Any]:
    """Freeze exact scenario, review, lineage, split, and overlap inputs."""
    root = Path(root)
    lineage_path, lineage = _load_required_json(root, "lineage-index.json")
    split_path, split = _load_required_json(root, "split-index.json")
    overlap_path, overlap = _load_required_json(root, "overlap-audit.json")
    source_configurations = _configurations(root)
    if lineage != build_lineage_index(root):
        raise ValidationError("lineage index does not match current scenarios")
    if split != build_split_index(root):
        raise ValidationError("split index does not match current scenarios")
    _validate_overlap_audit(overlap, source_configurations)

    configurations: dict[str, dict[str, Any]] = {}
    all_records: list[dict[str, Any]] = []
    review_status_counts: Counter[str] = Counter()
    for track, language, records in source_configurations:
        source_dir = root / track / language
        manifest_path = source_dir / "review-status.json"
        if not manifest_path.exists():
            raise ValidationError(f"required artifact is missing: {manifest_path}")
        review = validate_v07_review_manifest(source_dir, manifest_path)
        if review["scenario_count"] != len(records):
            raise ValidationError(f"review manifest count does not match {track}/{language}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for record in records:
            if manifest["items"][record["scenario_id"]]["scenario_digest"] != record_digest(record):
                raise ValidationError(
                    f"review digest does not match current scenario {record['scenario_id']}"
                )
        review_status_counts.update(review["status_counts"])
        all_records.extend(records)

        files = []
        for path in sorted(source_dir.glob("*.jsonl")):
            file_records = load_scenarios(path)
            files.append(
                {
                    "path": str(path.relative_to(root)),
                    "scenario_count": len(file_records),
                    "sha256": _file_digest(path),
                }
            )
        name = CONFIGURATION_NAMES[(track, language)]
        configurations[name] = {
            "benchmark_track": track,
            "language": language,
            "scenario_count": len(records),
            "category_counts": dict(
                sorted(Counter(record["category"] for record in records).items())
            ),
            "language_counts": {language: len(records)},
            "review_status_counts": review["status_counts"],
            "files": files,
            "review_manifest": {
                "path": str(manifest_path.relative_to(root)),
                "sha256": _file_digest(manifest_path),
            },
        }

    return {
        "index_version": "0.1",
        "benchmark_version": "0.7",
        "configuration_count": len(configurations),
        "scenario_count": len(all_records),
        "category_counts": dict(
            sorted(Counter(record["category"] for record in all_records).items())
        ),
        "language_counts": dict(
            sorted(Counter(record["language"] for record in all_records).items())
        ),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "artifacts": {
            "lineage": {
                "path": lineage_path.name,
                "sha256": _file_digest(lineage_path),
            },
            "overlap": {
                "path": overlap_path.name,
                "sha256": _file_digest(overlap_path),
            },
            "split": {
                "path": split_path.name,
                "sha256": _file_digest(split_path),
            },
        },
        "configurations": dict(sorted(configurations.items())),
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    """Atomically write a deterministic, human-readable JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            temporary_path = temporary.name
            json.dump(value, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and Path(temporary_path).exists():
            Path(temporary_path).unlink()
