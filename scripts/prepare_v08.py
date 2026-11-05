#!/usr/bin/env python3
"""Prepare the English-only v0.8 corpus using installed package helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from humanai_impact_bench.v08_dataset import prepare_v08


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/scenarios/v0.7"))
    parser.add_argument("--output", type=Path, default=Path("data/scenarios/v0.8"))
    args = parser.parse_args()
    result = prepare_v08(args.source, args.output)
    print(json.dumps({"scenario_count": result["scenario_count"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
