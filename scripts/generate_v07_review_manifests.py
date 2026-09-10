#!/usr/bin/env python3
"""Generate digest-bound draft review manifests for v0.7 configurations."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from humanai_impact_bench.review import REVIEW_STATUSES, derive_review_status, scenario_digest
from humanai_impact_bench.validation import ValidationError, load_scenarios

ROOT = Path(__file__).resolve().parents[1]
V07_ROOT = ROOT / "data" / "scenarios" / "v0.7"


def _load_scenarios(source_dir: str | Path) -> list[dict[str, Any]]:
    source = Path(source_dir)
    paths = sorted(source.glob("*.jsonl")) if source.is_dir() else [source]
    if not paths:
        raise ValidationError(f"no JSONL scenario files found in {source}")
    return [scenario for path in paths for scenario in load_scenarios(path)]


def build_manifest(
    source_dir: str | Path,
    track: str,
    language: str,
    existing_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a v0.2 manifest, preserving only digest-matched review events."""
    if track not in {"core", "agentic"}:
        raise ValidationError("track must be 'core' or 'agentic'")
    if language not in {"en", "vi"}:
        raise ValidationError("language must be 'en' or 'vi'")
    scenarios = _load_scenarios(source_dir)
    if {scenario["benchmark_version"] for scenario in scenarios} != {"0.7"}:
        raise ValidationError("v0.7 review manifests require v0.7 scenarios")
    if {scenario["benchmark_track"] for scenario in scenarios} != {track}:
        raise ValidationError("track does not match scenario data")
    if {scenario["language"] for scenario in scenarios} != {language}:
        raise ValidationError("language does not match scenario data")

    existing_items = (
        existing_manifest.get("items", {})
        if isinstance(existing_manifest, dict) and isinstance(existing_manifest.get("items"), dict)
        else {}
    )
    items: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        if scenario_id in items:
            raise ValidationError(f"duplicate v0.7 {language} scenario ID: {scenario_id}")
        digest = scenario_digest(scenario)
        existing_item = existing_items.get(scenario_id)
        events = (
            existing_item["review_events"]
            if isinstance(existing_item, dict)
            and existing_item.get("scenario_digest") == digest
            and isinstance(existing_item.get("review_events"), list)
            else []
        )
        author_ids = existing_item.get("author_ids") if isinstance(existing_item, dict) else None
        items[scenario_id] = {
            "scenario_digest": digest,
            "status": derive_review_status(scenario, events, author_ids=author_ids),
            "review_events": events,
        }
        if author_ids is not None:
            items[scenario_id]["author_ids"] = author_ids

    return {
        "manifest_version": "0.2",
        "benchmark_version": "0.7",
        "benchmark_track": track,
        "language": language,
        "scenario_count": len(scenarios),
        "allowed_statuses": sorted(REVIEW_STATUSES),
        "items": dict(sorted(items.items())),
    }


def write_manifest(
    source_dir: str | Path,
    output_path: str | Path,
    *,
    track: str,
    language: str,
) -> dict[str, Any]:
    """Regenerate a manifest and atomically replace its output file."""
    output = Path(output_path)
    existing = None
    if output.exists():
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"cannot preserve existing review manifest: invalid JSON: {exc.msg}"
            ) from exc
    manifest = build_manifest(source_dir, track, language, existing_manifest=existing)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=output.parent, delete=False
        ) as temporary:
            temporary_path = temporary.name
            json.dump(manifest, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, output)
    finally:
        if temporary_path is not None and Path(temporary_path).exists():
            Path(temporary_path).unlink()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--track", choices=("core", "agentic"))
    parser.add_argument("--language", choices=("en", "vi"))
    args = parser.parse_args()
    explicit = (args.source_dir, args.output, args.track, args.language)
    if any(explicit) and not all(explicit):
        parser.error("--source-dir, --output, --track, and --language must be used together")
    if all(explicit):
        write_manifest(args.source_dir, args.output, track=args.track, language=args.language)
        print(f"Wrote {args.output}")
        return 0

    generated = 0
    for track in ("core", "agentic"):
        for language in ("en", "vi"):
            source_dir = V07_ROOT / track / language
            if not source_dir.exists():
                continue
            output = source_dir / "review-status.json"
            write_manifest(source_dir, output, track=track, language=language)
            print(f"Wrote {output}")
            generated += 1
    if not generated:
        raise ValidationError(f"no v0.7 configuration directories found in {V07_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
