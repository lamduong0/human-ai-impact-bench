#!/usr/bin/env python3
"""Generate the frozen v0.7 configuration index."""

from __future__ import annotations

try:
    from scripts.v07_artifacts import V07_ROOT, build_configuration_index, write_json_atomic
except ModuleNotFoundError:  # Direct execution places scripts/ on sys.path.
    from v07_artifacts import V07_ROOT, build_configuration_index, write_json_atomic

OUTPUT_PATH = V07_ROOT / "configuration-index.json"


def main() -> int:
    write_json_atomic(OUTPUT_PATH, build_configuration_index())
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
