"""Digest-bound review evidence for v0.7 scenarios."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from humanai_impact_bench.validation import ValidationError, load_scenarios, utc_timestamp

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
    if event["reviewer_id"] != event["reviewer_id"].strip():
        raise ValidationError(f"{label}.reviewer_id must not contain surrounding whitespace")
    if event["review_type"] not in REVIEW_TYPES:
        raise ValidationError(f"{label}.review_type is not allowed")
    if event["decision"] not in DECISIONS:
        raise ValidationError(f"{label}.decision is not allowed")
    utc_timestamp(event["reviewed_at"], f"{label}.reviewed_at")
    if not _is_digest(event["scenario_digest"]):
        raise ValidationError(f"{label}.scenario_digest must be lowercase SHA-256")
    return event


def _latest_events(events: list[dict[str, str]]) -> list[dict[str, str]]:
    latest: dict[tuple[str, str, str], tuple[str, int, dict[str, str]]] = {}
    for index, event in enumerate(events):
        # Only the same reviewer in the same review scope can supersede their
        # own decision. Another approval cannot silently resolve an objection.
        key = (event["review_type"], event["reviewer_id"], event["reviewed_locale"])
        candidate = (event["reviewed_at"], index, event)
        if key not in latest or candidate[:2] > latest[key][:2]:
            latest[key] = candidate
    return [value[2] for value in latest.values()]


def _is_independent_approval(event: dict[str, str], author_ids: list[str]) -> bool:
    disclosure = " ".join(event["conflict_disclosure"].casefold().split())
    # These identities and qualifications are declarations, not authentication.
    # Unknown authorship cannot establish independent approval.
    return (
        bool(author_ids)
        and event["reviewer_id"] not in author_ids
        and disclosure in {"none", "no conflict", "no author conflict"}
    )


def _has_independent_construct(events: list[dict[str, str]], author_ids: list[str]) -> bool:
    return any(
        event["review_type"] == "construct"
        and event["decision"] == "approved"
        and _is_independent_approval(event, author_ids)
        for event in _latest_events(events)
    )


def derive_review_status(
    scenario: dict[str, Any], events: list[dict[str, Any]], *, author_ids: list[str] | None = None
) -> str:
    """Derive review maturity from events bound to the current scenario digest."""
    if not isinstance(events, list):
        raise ValidationError("review_events must be an array")
    author_ids = [] if author_ids is None else author_ids
    if (
        not isinstance(author_ids, list)
        or any(
            not isinstance(value, str) or not value.strip() or value != value.strip()
            for value in author_ids
        )
        or len(author_ids) != len(set(author_ids))
    ):
        raise ValidationError("author_ids must contain distinct non-empty declared author IDs")
    validated = [
        _validate_event(event, f"review_events[{index}]") for index, event in enumerate(events)
    ]
    digest = scenario_digest(scenario)
    current = [event for event in validated if event["scenario_digest"] == digest]
    if not current:
        return "draft_unreviewed"

    latest = _latest_events(current)
    if any(event["decision"] == "changes_requested" for event in latest):
        return "changes_requested"

    required = {"construct"}
    if scenario["language"] == "vi":
        required.add("locale")
    if scenario["risk_level"] in {
        "high",
        "critical",
    } or "requires-specialist-review" in scenario.get("tags", []):
        required.add("specialist_safety")
    approvals = {
        event["review_type"]
        for event in latest
        if event["decision"] == "approved"
        and _is_independent_approval(event, author_ids)
        and (event["review_type"] != "locale" or event["reviewed_locale"] == "vi-VN")
    }
    if not required <= approvals:
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
        if (
            not isinstance(item, dict)
            or not _ITEM_FIELDS <= set(item)
            or set(item) - _ITEM_FIELDS - {"author_ids"}
        ):
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
        author_ids = item.get("author_ids")
        status = derive_review_status(scenario, events, author_ids=author_ids)
        if item["scenario_digest"] != current_digest and item["status"] != "draft_unreviewed":
            raise ValidationError(
                f"review item {scenario_id} is stale and must store status 'draft_unreviewed'"
            )
        if item["scenario_digest"] == current_digest and item["status"] != status:
            current_events = [
                event for event in validated_events if event["scenario_digest"] == current_digest
            ]
            if item["status"] in {"reviewed", "release_ready"} and not (
                _has_independent_construct(current_events, author_ids or [])
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


def validate_v08_review_manifest(
    scenarios_path: str | Path,
    manifest_path: str | Path | dict[str, Any],
) -> dict[str, Any]:
    """Validate the intentionally draft-only English v0.8 manifest contract."""
    scenarios = _load_scenario_set(scenarios_path)
    manifest = _load_manifest(manifest_path)
    if set(manifest) != _MANIFEST_FIELDS:
        raise ValidationError("v0.8 review manifest has invalid fields")
    if manifest["manifest_version"] != "0.3" or manifest["benchmark_version"] != "0.8":
        raise ValidationError("v0.8 review requires manifest 0.3 and benchmark 0.8")
    if manifest["language"] != "en" or manifest["benchmark_track"] not in {"core", "agentic"}:
        raise ValidationError("v0.8 review requires an English core or agentic configuration")
    if manifest["allowed_statuses"] != ["draft_unreviewed"]:
        raise ValidationError("v0.8 automated-only review statuses must be draft_unreviewed")
    if any(
        r["benchmark_version"] != "0.8"
        or r["language"] != "en"
        or r["benchmark_track"] != manifest["benchmark_track"]
        for r in scenarios
    ):
        raise ValidationError("v0.8 review scope does not match scenario data")
    ids = [r["scenario_id"] for r in scenarios]
    if (
        len(ids) != len(set(ids))
        or not isinstance(manifest["items"], dict)
        or set(manifest["items"]) != set(ids)
    ):
        raise ValidationError("v0.8 review items must match unique scenario identities")
    if type(manifest["scenario_count"]) is not int or manifest["scenario_count"] != len(scenarios):
        raise ValidationError("v0.8 review scenario count mismatch")
    for row in scenarios:
        item = manifest["items"][row["scenario_id"]]
        if not isinstance(item, dict) or set(item) != _ITEM_FIELDS:
            raise ValidationError("v0.8 review item has invalid fields")
        if item["status"] != "draft_unreviewed" or item["review_events"] != []:
            raise ValidationError("v0.8 automated-only scenarios cannot claim human review")
        if item["scenario_digest"] != scenario_digest(row):
            raise ValidationError("v0.8 review scenario digest mismatch")
    return {
        "valid": True,
        "benchmark_version": "0.8",
        "benchmark_track": manifest["benchmark_track"],
        "language": "en",
        "scenario_count": len(scenarios),
        "status_counts": {"draft_unreviewed": len(scenarios)},
        "stale_review_count": 0,
    }
