#!/usr/bin/env python3
"""Rebuild digest-bound v0.7 overlap candidates without inventing review decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from humanai_impact_bench.validation import ValidationError, load_scenarios
from scripts.audit_scenario_coverage import _normalize, _prompt_signature, _sequence_signature
from scripts.audit_scenario_similarity import _pair_result
from scripts.audit_scenario_similarity import scenario_set_digest as historical_digest
from scripts.audit_template_phrases import _ngrams, _values
from scripts.v07_artifacts import (
    CONFIGURATION_NAMES,
    SELECTION_RULE,
    V07_ROOT,
    _lineage_tags,
    _validate_overlap_audit,
    build_split_index,
    load_v07_configuration,
    record_digest,
    scenario_set_digest,
    single_tag,
    write_json_atomic,
)

QUARANTINED = {"minor_safety", "self_harm_and_suicide"}
HISTORICAL_CATEGORIES = {
    "cross_session_memory_governance": {
        "memory_consent_and_personalization",
        "privacy_and_boundaries",
        "assistant_planted_memory",
        "false_shared_memory",
    },
    "personalized_persuasion_and_steering": {
        "personalized_vulnerability_exploitation",
        "engagement_manipulation",
        "ideological_steering",
        "identity_and_dignity_harm",
        "compulsive_use_and_displacement",
    },
    "delegated_action_authorization": {
        "autonomy_and_decisions",
        "institutional_authority_and_workplace_coercion",
    },
    "trajectory_recovery_and_correction": {
        "cross_session_dependency_and_recovery",
        "dependency_boundaries",
        "trust_and_anthropomorphism",
        "reality_testing",
        "assistant_planted_memory",
        "false_shared_memory",
        "moral_outsourcing_and_deskilling",
    },
}
TEXT_FIELDS = ("initial_prompt", "follow_up_prompts", "expected_behaviors", "failure_modes")


def identity(record: dict[str, Any]) -> str:
    return "/".join(
        (
            record["benchmark_version"],
            record.get("benchmark_track", "legacy"),
            record["language"],
            record["scenario_id"],
        )
    )


def _history(root: Path, issues: list[str]) -> tuple[list[dict], list[dict]]:
    records, sources = [], []
    seen = set()
    for version in ("0.1", "0.2", "0.3", "0.4", "0.5", "0.6"):
        directory = root.parent / f"v{version}"
        for path in sorted(directory.rglob("*.jsonl")):
            if "pending-safety-review" in path.resolve().parts or not path.resolve().is_relative_to(
                directory.resolve()
            ):
                issues.append(f"quarantined or escaped historical path: {path}")
                continue
            try:
                loaded = load_scenarios(path)
            except ValidationError as exc:
                issues.append(f"invalid historical source: {exc}")
                continue
            sources.append(
                {
                    "path": str(path.relative_to(root.parent)),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "scenario_count": len(loaded),
                }
            )
            for record in loaded:
                key = identity(record)
                if record["category"] in QUARANTINED:
                    issues.append(f"quarantined historical identity excluded: {key}")
                elif record["benchmark_version"] != version or key in seen:
                    issues.append(f"historical version/identity mismatch: {key}")
                else:
                    records.append(record)
                    seen.add(key)
    return records, sources


def _controlled(record: dict) -> dict:
    return {
        key: (
            [tag for tag in value if not tag.startswith(("protocol-", "source-scenario-"))]
            if key == "tags"
            else value
        )
        for key, value in record.items()
        if key not in {"scenario_id", "protocol_mode", "prefill_messages"}
    }


def _text_units(configurations, issues):
    units, equivalent = [], {}
    for track, language, records in configurations:
        if track == "core":
            units.extend({"record": r, "members": [identity(r)]} for r in records)
            continue
        pairs = defaultdict(list)
        for record in records:
            pairs[record["matched_pair_id"]].append(record)
        for pair_id, members in sorted(pairs.items()):
            valid = len(members) == 2 and {r["protocol_mode"] for r in members} == {
                "control",
                "prefill_stress",
            }
            if valid:
                valid = _controlled(members[0]) == _controlled(members[1])
            if not valid:
                issues.append(f"invalid matched pair {track}/{language}/{pair_id}")
                units.extend({"record": r, "members": [identity(r)]} for r in members)
                continue
            control = next(r for r in members if r["protocol_mode"] == "control")
            stress = next(r for r in members if r["protocol_mode"] == "prefill_stress")
            keys = sorted(identity(r) for r in members)
            units.append(
                {
                    "record": control,
                    "members": keys,
                    "prefill": stress["prefill_messages"],
                    "prefill_members": [identity(stress)],
                }
            )
            for key in keys:
                equivalent[key] = identity(control)
    return units, equivalent


def _prefill_fields(unit):
    messages = unit.get("prefill", unit["record"].get("prefill_messages", []))
    fields = defaultdict(list)
    for message in messages:
        fields["prefill_" + message["role"]].append(message["content"])
    if messages:
        fields["prefill_sequence"] = [
            "\x1f".join(
                message["role"] + ":" + _normalize(message["content"]) for message in messages
            )
        ]
    return fields


def _ancestry(current, historical, issues):
    records = {identity(r): r for r in [*historical, *current]}
    edges = {}
    for record in records.values():
        key = identity(record)
        if record["benchmark_version"] == "0.7":
            try:
                _family, _context, derivation, version, source_id = _lineage_tags(record)
            except ValidationError as exc:
                issues.append(f"invalid ancestry {key}: {exc}")
                continue
            if derivation == "authored-new":
                continue
        else:
            versions = [
                t.removeprefix("source-version-")
                for t in record["tags"]
                if t.startswith("source-version-")
            ]
            source_ids = [
                t.removeprefix("source-scenario-")
                for t in record["tags"]
                if t.startswith("source-scenario-")
            ]
            if not versions and not source_ids:
                continue
            if len(versions) != 1 or len(source_ids) != 1:
                issues.append(f"ambiguous historical ancestry: {key}")
                continue
            version, source_id = versions[0].removeprefix("v").replace("-", "."), source_ids[0]
            if version >= record["benchmark_version"]:
                issues.append(f"cyclic or nonhistorical ancestry: {key}")
                continue
        source_language = "en" if version == "0.7" else record["language"]
        source_track = record["benchmark_track"] if version == "0.7" else "legacy"
        source = f"{version}/{source_track}/{source_language}/{source_id}"
        if source not in records:
            issues.append(f"unresolved or quarantined source: {key} -> {source}")
            continue
        edges[key] = source
        if version == "0.7":
            original = records[source]
            for field in ("category", "risk_level", "dimensions", "protocol_mode"):
                if record.get(field) != original.get(field):
                    issues.append(f"bilingual alignment mismatch {key}: {field}")
            for prefix in ("concept-family-", "context-"):
                if single_tag(record, prefix) != single_tag(original, prefix):
                    issues.append(f"bilingual alignment mismatch {key}: {prefix}")
            if "requires-cultural-review" not in record["tags"]:
                issues.append(f"missing cultural-review requirement: {key}")
    return records, edges


def build_report(v07_root: Path) -> dict[str, Any]:
    """Recompute candidates and carry forward only digest-current explicit decisions."""
    root = Path(v07_root)
    issues = []
    configurations = []
    for track in ("core", "agentic"):
        for language in ("en", "vi"):
            try:
                configurations.append(
                    (track, language, load_v07_configuration(track, language, root))
                )
            except ValidationError as exc:
                issues.append(str(exc))
    current = [r for _, _, records in configurations for r in records]
    historical, historical_sources = _history(root, issues)
    units, equivalent = _text_units(configurations, issues)
    records, edges = _ancestry(current, historical, issues)
    expected_splits = None
    try:
        expected_splits = build_split_index(root)
        family_splits = defaultdict(set)
        for item in expected_splits["items"]:
            family_splits[item["concept_family_id"]].add(item["split"])
        for family, splits in sorted(family_splits.items()):
            if len(splits) > 1:
                issues.append(f"concept-family split leakage: {family} spans {sorted(splits)}")
        existing_split = root / "split-index.json"
        if existing_split.exists() and json.loads(existing_split.read_text()) != expected_splits:
            issues.append(
                "split index differs from the current concept-family split rule; "
                "possible split leakage"
            )
    except (ValidationError, json.JSONDecodeError) as exc:
        issues.append(f"split validation: {exc}")

    # Merge repeated findings for the same membership into one inspectable
    # candidate, while retaining every component/phrase that triggered it.
    findings = defaultdict(set)

    def add(kind, members, evidence):
        members = tuple(sorted(set(members)))
        if len(members) >= 2:
            findings[kind, members].add(evidence)

    for target, source in sorted(edges.items()):
        if target.startswith("0.7/"):
            add(
                "declared_ancestry",
                [target, source],
                f"Declared source edge {target} -> {source}; "
                f"target digest {record_digest(records[target])}; "
                f"source digest {record_digest(records[source])}.",
            )

    exact = defaultdict(list)
    for unit in [*units, *({"record": r, "members": [identity(r)]} for r in historical)]:
        record = unit["record"]
        signatures = [
            ("exact_prompt", "prompt_bundle", _prompt_signature(record)),
            ("exact_component", "context", _normalize(record["context"])),
        ]
        for field in TEXT_FIELDS:
            values = record[field] if isinstance(record[field], list) else [record[field]]
            signatures.extend(("exact_component", field, _normalize(value)) for value in values)
            if isinstance(record[field], list):
                signatures.append(
                    ("exact_component", field + "_sequence", _sequence_signature(values))
                )
        for signature in set(signatures):
            exact[(record["language"], *signature)].append(unit)
        history_unit = {
            "record": record,
            "members": unit.get("prefill_members", unit["members"]),
        }
        for field, values in _prefill_fields(unit).items():
            for value in {_normalize(value) for value in values}:
                exact[record["language"], "exact_component", field, value].append(history_unit)
    for (_language, kind, field, signature), group in exact.items():
        if len(group) > 1 and any(u["record"]["benchmark_version"] == "0.7" for u in group):
            add(kind, [m for u in group for m in u["members"]], f"{field}: {signature}")

    phrases = defaultdict(list)
    for unit in units:
        record = unit["record"]
        size = 14 if record["language"] == "vi" else 7
        components = {field: _values(record, (field,)) for field in TEXT_FIELDS}
        components.update(
            {
                field: values
                for field, values in _prefill_fields(unit).items()
                if field != "prefill_sequence"
            }
        )
        for field, values in components.items():
            found = set()
            for value in values:
                found.update(_ngrams(value, size))
            member_unit = (
                unit
                if not field.startswith("prefill_")
                else {"record": record, "members": unit.get("prefill_members", unit["members"])}
            )
            for phrase in found:
                phrases[
                    record["benchmark_track"], record["language"], record["category"], field, phrase
                ].append(member_unit)
    for (*_scope, field, phrase), group in phrases.items():
        if len(group) >= 3:
            add(
                "template_phrase",
                [m for u in group for m in u["members"]],
                f"{field}: {' '.join(phrase)}",
            )

    groups = defaultdict(list)
    for unit in units:
        r = unit["record"]
        groups[r["benchmark_track"], r["language"], r["category"]].append(unit)
    comparisons = Counter()
    for (_track, language, category), group in sorted(groups.items()):
        historical_categories = HISTORICAL_CATEGORIES.get(category, {category})
        previous = [
            {"record": r, "members": [identity(r)]}
            for r in historical
            if r["language"] == language and r["category"] in historical_categories
        ]
        pairs = (
            (left, right, "within_configuration_category") for left, right in combinations(group, 2)
        )
        cross = ((left, right, "current_vs_history") for left in group for right in previous)
        for batch in (pairs, cross):
            for left, right, scope in batch:
                comparisons[scope] += 1
                match = _pair_result(
                    left["record"],
                    right["record"],
                    sequence_threshold=0.58,
                    jaccard_threshold=0.45,
                    scope=scope,
                )
                if match is not None:
                    add(
                        "lexical_similarity",
                        [*left["members"], *right["members"]],
                        f"{scope}; sequence_ratio={match['sequence_ratio']}; "
                        f"token_jaccard={match['token_jaccard']}; source categories "
                        f"{left['record']['category']} / {right['record']['category']}.",
                    )

    candidates = []
    for (kind, members), details in sorted(findings.items()):
        payload = {"kind": kind, "members": list(members), "evidence": "\n".join(sorted(details))}
        candidates.append({"candidate_id": record_digest(payload), **payload})
    current_digests = {
        CONFIGURATION_NAMES[track, language]: scenario_set_digest(records)
        for track, language, records in configurations
    }
    history_sha = historical_digest(historical)
    resolutions = {}

    def ancestors(member):
        found = set()
        while member not in found:
            found.add(member)
            source = edges.get(member)
            if source is None:
                break
            member = source
        return {equivalent.get(key, key) for key in found}

    for candidate in candidates:
        members = {equivalent.get(m, m) for m in candidate["members"]}
        if candidate["kind"] == "declared_ancestry" or any(
            members <= ancestors(m) for m in candidate["members"]
        ):
            resolutions[candidate["candidate_id"]] = {
                "candidate_id": candidate["candidate_id"],
                "decision": "source_preserving",
                "rationale": (
                    "Every member lies on one verified declared source chain (including only "
                    "structurally verified paired equivalents). This records intentional source "
                    "ancestry, not independent human review or semantic equivalence of every "
                    "revised sentence."
                ),
            }
    old_path = root / "overlap-audit.json"
    stale_resolution_count = 0
    if old_path.exists():
        try:
            old = json.loads(old_path.read_text())
            if not isinstance(old, dict):
                raise ValueError("prior report must be an object")
        except (OSError, ValueError) as exc:
            issues.append(f"invalid prior resolution artifact: {exc}")
            old = {}
        prior = old.get("resolutions", [])
        if (
            old.get("configuration_sha256") != current_digests
            or old.get("historical_sha256") != history_sha
        ):
            stale_resolution_count = len(prior) if isinstance(prior, list) else 0
        elif not isinstance(prior, list):
            issues.append("resolution list in prior report is invalid")
        else:
            candidate_ids = {c["candidate_id"] for c in candidates}
            seen = set()
            for resolution in prior:
                if not isinstance(resolution, dict) or set(resolution) != {
                    "candidate_id",
                    "decision",
                    "rationale",
                }:
                    issues.append("invalid prior resolution fields")
                    continue
                cid = resolution["candidate_id"]
                if (
                    not isinstance(cid, str)
                    or cid not in candidate_ids
                    or cid in seen
                    or not isinstance(resolution["decision"], str)
                    or resolution["decision"]
                    not in {"revised", "accepted_distinct", "source_preserving"}
                    or not isinstance(resolution["rationale"], str)
                    or not resolution["rationale"].strip()
                ):
                    issues.append(f"invalid, duplicate or mismatched prior resolution: {cid}")
                    continue
                seen.add(cid)
                resolutions[cid] = resolution
    unresolved = sorted(
        c["candidate_id"] for c in candidates if c["candidate_id"] not in resolutions
    )
    report = {
        "audit_version": "0.1",
        "benchmark_version": "0.7",
        "scenario_count": len(current),
        "text_unit_count": len(units),
        "current_prefill_record_count": sum(bool(_prefill_fields(unit)) for unit in units),
        "configuration_sha256": current_digests,
        "historical_scenario_count": len(historical),
        "historical_sha256": history_sha,
        "historical_sources": historical_sources,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "resolutions": [resolutions[key] for key in sorted(resolutions)],
        "unresolved_candidate_ids": unresolved,
        "unresolved_candidate_count": len(unresolved),
        "stale_resolution_count": stale_resolution_count,
        "structural_issues": sorted(set(issues)),
        "valid": not issues and not unresolved,
        "split_rule": SELECTION_RULE,
        "expected_split_sha256": record_digest(expected_splits) if expected_splits else None,
        "scope": {
            "exact": (
                "All current text units against one another and v0.1-v0.6 in the same language; "
                "context, prompts, rubric items and separate role-aware prefills are screened; "
                "historical-only groups omitted. Prefill membership names only stress records."
            ),
            "templates": (
                "Within track/language/category; 7 English or 14 Vietnamese tokens repeated "
                "in at least 3 distinct text units, including adapted records and separate "
                "prefill user/assistant messages."
            ),
            "lexical": (
                "Visible user prompt bundles only: within track/language/category and current "
                "versus matching historical categories, "
                "with explicit legacy construct mapping for new agentic categories."
            ),
            "agentic_historical_categories": {
                key: sorted(value) for key, value in HISTORICAL_CATEGORIES.items()
            },
            "sequence_threshold": 0.58,
            "token_jaccard_threshold": 0.45,
            "lexical_comparisons": dict(comparisons),
        },
        "limitations": [
            "Lexical screening does not establish semantic/cultural validity or independence.",
            "Pair and bilingual checks verify structural alignment, not translation meaning.",
            "Source-preserving dispositions check provenance; they are not human approvals.",
            "Unknown candidates remain unresolved until given a candidate-specific disposition.",
            "No quarantined records are included in comparison input.",
        ],
    }
    if report["valid"]:
        _validate_overlap_audit(report, configurations)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=V07_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = build_report(args.root)
        if args.output:
            write_json_atomic(args.output, report)
            print(
                json.dumps(
                    {
                        key: report[key]
                        for key in (
                            "valid",
                            "scenario_count",
                            "candidate_count",
                            "unresolved_candidate_count",
                            "structural_issues",
                        )
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["valid"] else 1
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
