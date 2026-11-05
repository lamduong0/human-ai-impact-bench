# HumanAI-Impact-Bench

[![CI](https://github.com/lamduong0/human-ai-impact-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/lamduong0/human-ai-impact-bench/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/human-ai-impact-bench)](https://pypi.org/project/human-ai-impact-bench/)
[![Python](https://img.shields.io/pypi/pyversions/human-ai-impact-bench)](https://pypi.org/project/human-ai-impact-bench/)
[![Dataset](https://img.shields.io/badge/Hugging%20Face-dataset-yellow)](https://huggingface.co/datasets/lamduong/human-ai-impact-bench-scenarios)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

HumanAI-Impact-Bench evaluates conversational AI behavior related to emotion,
autonomy, cognition, trust, and social connection. Scripted multi-turn scenarios
probe dependency reinforcement, sycophancy, manipulation, unsupported beliefs,
memory claims, and failures to preserve the user's agency.

**Research preview.** Automated results are **PREVIEW** behavioral evidence.
They do not establish clinical safety, production readiness, or causal effects
on human well-being.

[Quick start](#quick-start) · [Evaluation guide](docs/v0.8-evaluation-guide.md) ·
[Results](docs/results/README.md) · [Dataset history](docs/dataset-history.md)

## What is included

- Multi-turn scenarios with expected behaviors, failure modes, and explicit rubrics.
- Separate core and agentic tracks; agentic cases compare control and synthetic
  prior-history stress conditions.
- Thirteen scoring dimensions and explicit critical-failure labels, with
  per-dimension support and transparent penalties.
- English-only v0.8 study tooling for Chat Completions and Responses APIs,
  bounded request budgets, judge diagnostics, and artifact verification.
- Versioned source lineage, concept-family splits, and review manifests.

Agentic probes assess conversational behavior. Synthetic history does not test
real product memory or observed tool execution.

## Current status

**v0.8 is the English-only development revision in this checkout.**

| Configuration | Records | Coverage | Review status |
|---|---:|---|---|
| `v0.8-core-en` | 2,400 | 24 categories | `draft_unreviewed` |
| `v0.8-agentic-en` | 400 | 4 categories; 200 matched pairs | `draft_unreviewed` |

A deterministic **64-record pilot** covers both tracks. **192 synthetic
response transcripts** provide judge diagnostics; they are authored hypotheses,
not human gold labels or additional scenario records.

The latest live pilot stopped after HTTP 429 responses and token-truncated
outputs. Its incomplete coverage cannot support a model ranking. See the
[2026-11-05 run summary](docs/results/v0.8-2026-11-05.md) and
[evidence status](docs/v0.8-results-status.md).

Earlier English/Vietnamese datasets and their review history remain available.
See [dataset history](docs/dataset-history.md) for counts and version details,
and [Hugging Face](https://huggingface.co/datasets/lamduong/human-ai-impact-bench-scenarios)
for hosted configurations. Local v0.8 preparation does not imply publication.

## Quick start

Python **3.10+** is required; the package has no mandatory runtime dependencies.
Install from this development checkout and validate each English track:

```bash
python -m pip install -e .
humanai-impact-bench validate data/scenarios/v0.8/core/en
humanai-impact-bench validate data/scenarios/v0.8/agentic/en
```

Score the included annotation example:

```bash
humanai-impact-bench score examples/annotations.jsonl --pretty
```

For the published package, use `python -m pip install human-ai-impact-bench`.
Dataset and package versions are separate; development commands may require
installation from this checkout. Scenarios are distributed through the repository
and Hugging Face.

## Run an evaluation

1. Choose one track and freeze its source, selection, prompts, and model settings.
2. Configure the [v0.8 study template](configs/v0.8-study-template.json) with
   candidate/judge endpoints, credential environment-variable names, and budgets.
3. Dry-run the plan to check coverage and request limits, then execute it.
4. Produce per-judge reports and verify the bundle against captured artifacts.

The [evaluation guide](docs/v0.8-evaluation-guide.md) contains the complete commands,
API options, audit workflow, and report interpretation. Keep keys in environment
variables and local transcripts under the ignored `.local-runs/` directory.

## Interpret results correctly

- Keep core/agentic, language, and calibration/public-evaluation results separate.
- Compare candidates using the same source and judging procedure; disclose
  self-judging and differences in generation settings.
- Report critical failures, missing results, and concept-family support alongside
  aggregate scores. Physical record counts are not independent observations.
- Artifact verification establishes internal consistency, not judge accuracy or
  human validation. v0.8 has no deployment policy; its deployment action is `HOLD`.
- Human ratings and studies of effects on people are separate research activities.

Detailed historical scores live in the [results archive](docs/results/README.md).
They are dated snapshots, not a current leaderboard.

## Documentation

| Topic | Guide |
|---|---|
| Run, audit, and verify v0.8 | [Evaluation guide](docs/v0.8-evaluation-guide.md) |
| Current evidence and limitations | [Evidence status](docs/v0.8-results-status.md) |
| Scoring dimensions and weights | [Benchmark card](docs/benchmark-card.md#dimensions-and-weights) |
| Human annotation | [Annotation guide](docs/annotation-guide.md) |
| Version-specific deployment gates | [Deployment gate](docs/deployment-gate.md) |
| Dataset versions and review history | [Dataset history](docs/dataset-history.md) |
| Current and archived evaluations | [Results index](docs/results/README.md) |
| Research design and validation | [Research protocol](docs/research-protocol.md) · [Validation plan](docs/validation-plan.md) |
| Related research | [Related work](docs/related-work.md) |
| Coding-agent workflow | [Agent skill](skills/humanai-impact-bench/SKILL.md) |

## Contribute and license

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributions and review requirements.
Code and data are licensed under [Apache-2.0](LICENSE).
