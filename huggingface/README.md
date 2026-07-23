---
license: apache-2.0
language:
  - en
  - vi
pretty_name: HumanAI-Impact-Bench Scenarios
size_categories:
  - n<1K
task_categories:
  - text-generation
  - text-classification
tags:
  - ai-safety
  - responsible-ai
  - human-ai-interaction
  - benchmark
  - evaluation
  - red-teaming
  - chatbot
  - emotional-safety
  - vietnamese
configs:
  - config_name: v0.1
    data_files:
      - split: en
        path: data/scenarios/v0.1/en.jsonl
      - split: vi
        path: data/scenarios/v0.1/vi.jsonl
  - config_name: v0.2
    data_files:
      - split: en
        path: data/scenarios/v0.2/en.jsonl
      - split: vi
        path: data/scenarios/v0.2/vi.jsonl
  - config_name: v0.3
    data_files:
      - split: en
        path: data/scenarios/v0.3/en.jsonl
  - config_name: v0.4
    data_files:
      - split: en
        path: data/scenarios/v0.4/*.jsonl
---

# HumanAI-Impact-Bench — Scenarios

Bilingual (English / Vietnamese) scenario set for evaluating how conversational
AI systems affect human **emotion, autonomy, cognition, trust, and social
connection**. Each record is a scripted multi-turn probe designed to surface
failure modes such as emotional dependency reinforcement, sycophancy, crisis
mishandling, false-memory agreement, and epistemic over-dependence.

- **Code / tooling:** https://github.com/lamduong0/human-ai-impact-bench
- **License:** Apache-2.0
- **Languages:** English (`en`), Vietnamese (`vi`)
- **Size:** 288 released scenarios across four benchmark revisions

> ⚠️ **This is a PREVIEW research benchmark.** It is an engineering risk-control
> and research artifact, **not** a clinical assessment, proof of safety, or
> evidence that a system improves human well-being. Automated results produced
> with these scenarios must never be represented as validated human-impact or
> psychological-safety certification.

## Configurations

| Config | Splits | Scenarios |
|--------|--------|-----------|
| `v0.1` | `en`, `vi` | 8 + 8 |
| `v0.2` | `en`, `vi` | 8 + 8 |
| `v0.3` | `en` | 200 |
| `v0.4` | `en` | 56 |

```python
from datasets import load_dataset

# English v0.3 expansion (200 scenarios)
ds = load_dataset("lamduong/human-ai-impact-bench-scenarios", "v0.3", split="en")

# English v0.4 authored expansion (56 scenarios)
v04 = load_dataset("lamduong/human-ai-impact-bench-scenarios", "v0.4", split="en")

# Bilingual v0.1
en = load_dataset("lamduong/human-ai-impact-bench-scenarios", "v0.1", split="en")
vi = load_dataset("lamduong/human-ai-impact-bench-scenarios", "v0.1", split="vi")
```

## Record schema

Each scenario is a JSON object with these fields (see
[`schemas/scenario.schema.json`](https://github.com/lamduong0/human-ai-impact-bench/blob/main/schemas/scenario.schema.json)):

| Field | Type | Description |
|-------|------|-------------|
| `benchmark_version` | string | `0.1` \| `0.2` \| `0.3` \| `0.4` |
| `scenario_id` | string | Stable kebab-case identifier |
| `language` | string | `en` \| `vi` |
| `title` | string | Short human-readable title |
| `category` | string | e.g. `dependency_boundaries`, `reality_testing`, `engagement_manipulation`, `identity_and_dignity_harm` (24 released categories) |
| `risk_level` | string | `low` \| `moderate` \| `high` \| `critical` |
| `context` | string | Situation description |
| `persona` | object | Age group, situation, communication style, vulnerability factors |
| `initial_prompt` | string | Opening user turn |
| `follow_up_prompts` | list[string] | Scripted subsequent user turns |
| `expected_behaviors` | list[string] | What a safe assistant should do |
| `failure_modes` | list[string] | Concrete unsafe behaviors to detect |
| `dimensions` | list[string] | Scored rubric dimensions |
| `tags` | list[string] | Free-form labels |

## Intended use

- Red-teaming and pre-release evaluation of chatbots / conversational agents.
- Comparing candidate models on human-impact dimensions.
- Prioritizing scenarios for human review.

**Out of scope:** clinical or psychological safety claims, production sign-off,
or any representation of automated scores as validated human outcomes.

## Review maturity and exclusions

The v0.3 and v0.4 English-first expansions are `draft_unreviewed`. Their
per-scenario review state is published in each revision's
`review-status.json`; neither revision is culturally validated. Automated
benchmark results remain **PREVIEW** evidence.

The repository also contains 22 sensitive v0.4 drafts awaiting dedicated
safety review. They are intentionally excluded from this dataset and from the
288-record total.

## How scenarios are used

The companion package runs each scenario against an OpenAI-compatible endpoint,
captures the multi-turn transcript, and (optionally) scores it with an LLM judge
under a pinned, auditable configuration, then gates the aggregate report against
a deterministic deployment policy. See the
[deployment-gate docs](https://github.com/lamduong0/human-ai-impact-bench/blob/main/docs/deployment-gate.md).

```bash
pip install human-ai-impact-bench   # tooling (scenarios distributed via this dataset / the repo)
```

## Citation

See [`CITATION.cff`](https://github.com/lamduong0/human-ai-impact-bench/blob/main/CITATION.cff)
in the source repository.

## Limitations & ethics

Scenarios intentionally depict vulnerable users (loneliness, grief, crisis,
distorted beliefs). They are fictional probes authored for evaluation, not real
user data. Vietnamese scenarios are authored/reviewed for cultural fit but
coverage is a preview; the English-first v0.3 and v0.4 expansions still require
independent cultural review. See the repo's cultural-review guide. Automated
judging can miss nuance and systematically over-score responses — a pass means
only that a captured candidate satisfied the configured automated policy.
