"""Digest-bound review evidence for v0.7 scenarios."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import ValidationError, load_scenarios

REVIEW_TYPES = {"construct", "locale", "specialist_safety", "release"}
DECISIONS = {"approved", "changes_requested"}
REVIEW_STATUSES = {
    "draft_unreviewed",
    "in_review",
    "changes_requested",
    "reviewed",
    "release_ready",
}
_EVENT_FIELDS = {
    "review_type",
    "reviewer_id",
    "qualification",
    "decision",
    "reviewed_at",
    "conflict_disclosure",
    "reviewed_locale",
    "notes",
    "scenario_digest",
}
_ITEM_FIELDS = {"scenario_digest", "status", "review_events"}
_MANIFEST_FIELDS = {
    "manifest_version",
    "benchmark_version",
    "benchmark_track",
    "language",
    "scenario_count",
    "allowed_statuses",
    "items",
}


def scenario_digest(record: dict[str, Any]) -> str:
    """Return the SHA-256 digest of canonical scenario JSON."""
    payload = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _is_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_event(event: Any, label: str) -> dict[str, str]:
    if not isinstance(event, dict) or set(event) != _EVENT_FIELDS:
        raise ValidationError(f"{label} has invalid fields")
    for field in _EVENT_FIELDS:
        if not isinstance(event[field], str) or not event[field].strip():
            raise ValidationError(f"{label}.{field} must be a non-empty string")
    if event["review_type"] not in REVIEW_TYPES:
        raise ValidationError(f"{label}.review_type is not allowed")
    if event["decision"] not in DECISIONS:
        raise ValidationError(f"{label}.decision is not allowed")
    try:
        datetime.strptime(event["reviewed_at"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValidationError(f"{label}.reviewed_at must be a UTC timestamp") from exc
    if not _is_digest(event["scenario_digest"]):
        raise ValidationError(f"{label}.scenario_digest must be lowercase SHA-256")
    return event


def _latest_events(events: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    latest: dict[str, tuple[str, int, dict[str, str]]] = {}
    for index, event in enumerate(events):
        key = event["review_type"]
        candidate = (event["reviewed_at"], index, event)
        if key not in latest or candidate[:2] > latest[key][:2]:
            latest[key] = candidate
    return {key: value[2] for key, value in latest.items()}


def _is_independent_construct(event: dict[str, str]) -> bool:
    disclosure = " ".join(event["conflict_disclosure"].casefold().split())
    return disclosure in {"none", "no conflict", "no author conflict"}


def _has_independent_construct(events: list[dict[str, str]]) -> bool:
    return any(
        event["review_type"] == "construct"
        and event["decision"] == "approved"
        and _is_independent_construct(event)
        for event in events
    )


def derive_review_status(scenario: dict[str, Any], events: list[dict[str, Any]]) -> str:
    """Derive review maturity from events bound to the current scenario digest."""
    if not isinstance(events, list):
        raise ValidationError("review_events must be an array")
    validated = [
        _validate_event(event, f"review_events[{index}]") for index, event in enumerate(events)
    ]
    digest = scenario_digest(scenario)
    current = [event for event in validated if event["scenario_digest"] == digest]
    if not current:
        return "draft_unreviewed"

    latest = _latest_events(current)
    if any(event["decision"] == "changes_requested" for event in latest.values()):
        return "changes_requested"

    required = {"construct"}
    if scenario["language"] == "vi":
        required.add("locale")
    if scenario["risk_level"] in {"high", "critical"}:
        required.add("specialist_safety")
    approvals = {
        review_type for review_type, event in latest.items() if event["decision"] == "approved"
    }
    if _has_independent_construct(current):
        approvals.add("construct")
    else:
        approvals.discard("construct")
    if not required <= approvals:
        return "in_review"
    if scenario["language"] == "vi" and latest["locale"]["reviewed_locale"] != "vi-VN":
        return "in_review"
    if "release" in approvals:
        return "release_ready"
    return "reviewed"


def _load_scenario_set(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_dir():
        return load_scenarios(source)
    files = sorted(source.glob("*.jsonl"))
    if not files:
        raise ValidationError(f"no JSONL scenario files found in {source}")
    return [scenario for scenario_file in files for scenario in load_scenarios(scenario_file)]


def _load_manifest(value: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    path = Path(value)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {path}") from exc
    except OSError as exc:
        raise ValidationError(f"could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc.msg}") from exc
    if not isinstance(manifest, dict):
        raise ValidationError("review manifest must be a JSON object")
    return manifest


def validate_v07_review_manifest(
    scenarios_path: str | Path,
    manifest_path: str | Path | dict[str, Any],
) -> dict[str, Any]:
    """Validate a v0.2 manifest and return its digest-current status summary."""
    scenarios = _load_scenario_set(scenarios_path)
    manifest = _load_manifest(manifest_path)
    if set(manifest) != _MANIFEST_FIELDS:
        raise ValidationError("v0.2 review manifest has invalid fields")
    if manifest["manifest_version"] != "0.2":
        raise ValidationError("review manifest_version must be '0.2'")
    if manifest["benchmark_version"] != "0.7":
        raise ValidationError("v0.2 review benchmark_version must be '0.7'")
    if manifest["benchmark_track"] not in {"core", "agentic"}:
        raise ValidationError("review benchmark_track must be 'core' or 'agentic'")
    if manifest["language"] not in {"en", "vi"}:
        raise ValidationError("review language must be 'en' or 'vi'")
    if not isinstance(manifest["scenario_count"], int) or isinstance(
        manifest["scenario_count"], bool
    ):
        raise ValidationError("review scenario_count must be an integer")
    if (
        not isinstance(manifest["allowed_statuses"], list)
        or set(manifest["allowed_statuses"]) != REVIEW_STATUSES
        or len(manifest["allowed_statuses"]) != len(REVIEW_STATUSES)
    ):
        raise ValidationError("review allowed_statuses do not match v0.2 statuses")
    if not isinstance(manifest["items"], dict):
        raise ValidationError("review items must be an object")

    scenario_ids = [scenario["scenario_id"] for scenario in scenarios]
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ValidationError("scenario IDs must be unique in a single-language review set")
    if set(manifest["items"]) != set(scenario_ids):
        raise ValidationError("review items do not match scenario IDs")
    if manifest["scenario_count"] != len(scenarios):
        raise ValidationError("review scenario_count does not match scenario data")
    if {scenario["benchmark_version"] for scenario in scenarios} != {"0.7"}:
        raise ValidationError("v0.2 review manifest requires v0.7 scenarios")
    if {scenario["benchmark_track"] for scenario in scenarios} != {manifest["benchmark_track"]}:
        raise ValidationError("review benchmark_track does not match scenario data")
    if {scenario["language"] for scenario in scenarios} != {manifest["language"]}:
        raise ValidationError("review language does not match scenario data")

    statuses: Counter[str] = Counter()
    stale_review_count = 0
    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        current_digest = scenario_digest(scenario)
        item = manifest["items"][scenario_id]
        if not isinstance(item, dict) or set(item) != _ITEM_FIELDS:
            raise ValidationError(f"review item {scenario_id} has invalid fields")
        if not _is_digest(item["scenario_digest"]):
            raise ValidationError(
                f"review item {scenario_id}.scenario_digest must be lowercase SHA-256"
            )
        if item["status"] not in REVIEW_STATUSES:
            raise ValidationError(f"review item {scenario_id} has unknown status")
        events = item["review_events"]
        if not isinstance(events, list):
            raise ValidationError(f"review item {scenario_id}.review_events must be an array")
        validated_events = [
            _validate_event(event, f"review item {scenario_id}.review_events[{index}]")
            for index, event in enumerate(events)
        ]
        stale_review_count += any(
            event["scenario_digest"] != current_digest for event in validated_events
        )
        status = derive_review_status(scenario, events)
        if item["scenario_digest"] != current_digest and item["status"] != "draft_unreviewed":
            raise ValidationError(
                f"review item {scenario_id} is stale and must store status 'draft_unreviewed'"
            )
        if item["scenario_digest"] == current_digest and item["status"] != status:
            current_events = [
                event for event in validated_events if event["scenario_digest"] == current_digest
            ]
            if item["status"] in {"reviewed", "release_ready"} and not (
                _has_independent_construct(current_events)
            ):
                raise ValidationError(
                    f"review item {scenario_id} lacks independent construct review"
                )
            raise ValidationError(
                f"review item {scenario_id}.status does not match review evidence"
            )
        statuses[status] += 1

    return {
        "valid": True,
        "benchmark_version": "0.7",
        "benchmark_track": manifest["benchmark_track"],
        "language": manifest["language"],
        "scenario_count": len(scenarios),
        "status_counts": dict(sorted(statuses.items())),
        "stale_review_count": stale_review_count,
    }
