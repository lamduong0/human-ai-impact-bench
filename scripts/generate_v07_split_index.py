#!/usr/bin/env python3
"""Generate deterministic concept-family split assignments for v0.7."""

from __future__ import annotations

try:
    from scripts.v07_artifacts import V07_ROOT, build_split_index, write_json_atomic
except ModuleNotFoundError:  # Direct execution places scripts/ on sys.path.
    from v07_artifacts import V07_ROOT, build_split_index, write_json_atomic

OUTPUT_PATH = V07_ROOT / "split-index.json"


def main() -> int:
    write_json_atomic(OUTPUT_PATH, build_split_index())
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
