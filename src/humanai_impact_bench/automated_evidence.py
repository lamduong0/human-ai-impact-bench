"""Verify internally consistent automated artifacts without promoting evidence."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from humanai_impact_bench.robustness import build_study_report
from humanai_impact_bench.validation import ValidationError

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = {"bundle_version", "manifest", "state", "report", "artifacts"}


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValidationError(f"non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        _nonfinite(value)
    return number


def _parse(text: str, label: str) -> Any:
    try:
        return json.loads(
            text, object_pairs_hook=_object, parse_constant=_nonfinite, parse_float=_finite_float
        )
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"{label}: invalid JSON: {exc}") from exc


def _load(path: Path) -> Any:
    try:
        return _parse(path.read_text(encoding="utf-8"), str(path))
    except (OSError, UnicodeError) as exc:
        raise ValidationError(f"could not read artifact {path}: {exc}") from exc


def _safe_path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValidationError("artifact path must be a nonempty relative POSIX path")
    parts = PurePosixPath(value)
    if parts.is_absolute() or ".." in parts.parts or re.match(r"^[A-Za-z]:", value):
        raise ValidationError("artifact path must stay inside its bundle root")
    resolved = (root / value).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValidationError(
            "artifact path or symlink must resolve inside its bundle root"
        ) from exc
    return resolved


def _reference(root: Path, value: Any) -> tuple[Path, str]:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ValidationError("artifact reference must contain exactly path and sha256")
    digest = value["sha256"]
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise ValidationError("artifact digest must be lowercase SHA-256")
    path = _safe_path(root, value["path"])
    if not path.is_file():
        raise ValidationError(f"missing artifact file: {value['path']}")
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValidationError(f"cannot read artifact file: {value['path']}") from exc
    if actual != digest:
        raise ValidationError(f"artifact digest mismatch: {value['path']}")
    return path, digest


def _require_inventory(root: Path, value: str, inventory: dict[Path, str]) -> Path:
    path = _safe_path(root, value)
    if path not in inventory:
        raise ValidationError(f"referenced artifact absent from bundle inventory: {value}")
    return path


def _state_references(value: Any, root: Path, inventory: dict[Path, str]) -> None:
    if isinstance(value, list):
        for item in value:
            _state_references(item, root, inventory)
    elif isinstance(value, dict):
        if "path" in value and "sha256" in value:
            path = _require_inventory(root, value["path"], inventory)
            if value["sha256"] != inventory[path]:
                raise ValidationError("state artifact digest differs from bundle inventory")
        for key, item in value.items():
            if key in {"request", "response"} and isinstance(item, str):
                _require_inventory(root, item, inventory)
            _state_references(item, root, inventory)


def _manifest_references(value: Any, root: Path, inventory: dict[Path, str]) -> None:
    if isinstance(value, list):
        for item in value:
            _manifest_references(item, root, inventory)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key == "dataset_root" and isinstance(item, str):
                directory = _safe_path(root, item)
                if not directory.is_dir():
                    raise ValidationError("dataset_root must be an existing bundle directory")
                for path in directory.rglob("*"):
                    resolved = _safe_path(root, path.relative_to(root).as_posix())
                    if resolved.is_file() and resolved not in inventory:
                        raise ValidationError("dataset file absent from bundle inventory")
            elif (
                key in {"selection_path", "fixtures_path", "system_prompt_path"}
                and item is not None
            ):
                referenced = _require_inventory(root, item, inventory)
                if key == "fixtures_path":
                    companion = referenced.parent / "manifest.json"
                    _require_inventory(root, companion.relative_to(root).as_posix(), inventory)
            _manifest_references(item, root, inventory)


def _same(actual: Any, expected: Any, path: str = "report") -> None:
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        if type(actual) is not type(expected) or actual != expected:
            raise ValidationError(f"recomputed report mismatch at {path}")
    elif isinstance(expected, int):
        if type(actual) is not int or actual != expected:
            raise ValidationError(f"recomputed report mismatch at {path}")
    elif isinstance(expected, float):
        if (
            isinstance(actual, bool)
            or not isinstance(actual, (int, float))
            or not math.isfinite(actual)
            or not math.isfinite(expected)
            or not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9)
        ):
            raise ValidationError(f"recomputed report mismatch at {path}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValidationError(f"recomputed report mismatch at {path}")
        for index, (a, b) in enumerate(zip(actual, expected, strict=True)):
            _same(a, b, f"{path}[{index}]")
    elif isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValidationError(f"recomputed report fields mismatch at {path}")
        for key in expected:
            _same(actual[key], expected[key], f"{path}.{key}")
    else:
        raise ValidationError(f"unsupported recomputed report value at {path}")


def _validate_state(manifest: Path, root: Path) -> dict[str, Any]:
    from humanai_impact_bench.experiments import validate_study_state

    return validate_study_state(manifest, root)


def write_evidence_bundle(run_root: Path, report_path: Path, output_path: Path) -> dict[str, Any]:
    """Write a portable inventory of one study, rejecting path aliasing or escape."""
    root = Path(run_root).resolve()
    report = Path(report_path).resolve()
    output = Path(output_path).resolve()
    for path in (report, output):
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("bundle and report paths must be inside the study root") from exc
    if output.parent != root:
        raise ValidationError("bundle output must be directly in the study root")
    primary = {
        "manifest": root / "study.json",
        "state": root / "study-state.json",
        "report": report,
    }
    if output in primary.values() or len(set(primary.values())) != 3:
        raise ValidationError("bundle must not overwrite or alias primary study artifacts")
    if any(output.is_relative_to(root / name) for name in ("inputs", "tasks")):
        raise ValidationError("bundle output must not overwrite study inputs")

    def ref(path):
        if not path.is_file():
            raise ValidationError(f"missing bundle input: {path.name}")
        return {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    bundle = {
        "bundle_version": "0.8",
        **{name: ref(path) for name, path in primary.items()},
        "artifacts": [],
    }
    seen = set(primary.values())
    for item in sorted(root.rglob("*")):
        path = _safe_path(root, item.relative_to(root).as_posix())
        if path == output or item in primary.values() or not path.is_file():
            continue
        if path in seen:
            raise ValidationError("duplicate aliased file in bundle inventory")
        seen.add(path)
        # Keep lexical in-root references so escaping symlinks cannot be hidden.
        bundle["artifacts"].append(ref(item))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent, prefix=f".{output.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(bundle, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return bundle


def verify_automated_evidence(bundle_path: Path) -> dict[str, Any]:
    """Reconcile file hashes, actual run contents and recomputed report metrics.

    Hashes and provenance can establish internal consistency, not authenticate
    provider identities or prove that captured outputs came from a remote model.
    """
    bundle_path = Path(bundle_path).resolve()
    root = bundle_path.parent
    bundle = _load(bundle_path)
    if not isinstance(bundle, dict) or set(bundle) != _FIELDS or bundle["bundle_version"] != "0.8":
        raise ValidationError("automated evidence must use the exact v0.8 bundle contract")
    if not isinstance(bundle["artifacts"], list):
        raise ValidationError("bundle artifacts must be a list")
    inventory: dict[Path, str] = {}
    named: dict[str, Path] = {}
    references = [(name, bundle[name]) for name in ("manifest", "state", "report")]
    references += [("artifact", item) for item in bundle["artifacts"]]
    for name, ref in references:
        path, digest = _reference(root, ref)
        if path == bundle_path or path in inventory:
            raise ValidationError("duplicate or self-referential bundle artifact path")
        inventory[path] = digest
        if name != "artifact":
            named[name] = path
    if named["state"] != (root / "study-state.json").resolve():
        raise ValidationError("bundle state must reference the validated study-state.json")
    manifest = _load(named["manifest"])
    state = _load(named["state"])
    report = _load(named["report"])
    if not all(isinstance(v, dict) for v in (manifest, state, report)):
        raise ValidationError("manifest, state and report must be JSON objects")
    _manifest_references(manifest, root, inventory)
    _state_references(state, root, inventory)
    for path in inventory:
        if path.suffix == ".json":
            _load(path)
        elif path.suffix == ".jsonl":
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError) as exc:
                raise ValidationError(f"could not read JSONL artifact: {path}") from exc
            for number, line in enumerate(lines, 1):
                if line.strip():
                    _parse(line, f"{path}:{number}")
    validated = _validate_state(named["manifest"], root)
    if validated["manifest"] != manifest:
        raise ValidationError("validated manifest differs from the bundle manifest")
    expected = build_study_report(validated)
    actual = {key: value for key, value in report.items() if key != "generated_at"}
    _same(actual, expected)
    return {
        "tool": "HumanAI-Impact-Bench",
        "bundle_version": "0.8",
        "artifact_integrity": "verified",
        "verified_artifacts": len(inventory),
        "execution_status": validated["execution_status"],
        "evidence_stage": "PREVIEW",
        "human_review": "not_performed",
        "deployment_action": "HOLD",
        "provider_authenticity": "not_established_by_artifact_verification",
        "comparison_complete": expected["comparison_complete"],
    }
