"""HumanAI-Impact-Bench."""

from humanai_impact_bench.scoring import BenchmarkResult, score_annotations
from humanai_impact_bench.validation import (
    ValidationError,
    load_annotations,
    load_scenarios,
)

__all__ = [
    "BenchmarkResult",
    "ValidationError",
    "load_annotations",
    "load_scenarios",
    "score_annotations",
]

__version__ = "0.1.0"
