---
license: apache-2.0
language:
  - en
  - vi
pretty_name: HumanAI-Impact-Bench Scenarios
size_categories:
  - 1K<n<10K
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
  - config_name: v0.5
    data_files:
      - split: en
        path: data/scenarios/v0.5/*.jsonl
  - config_name: v0.6
    data_files:
      - split: en
        path: data/scenarios/v0.6/en/*.jsonl
      - split: vi
        path: data/scenarios/v0.6/vi/*.jsonl
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
- **Size:** 1,888 scenarios across six benchmark revisions: 288 released
  records and 1,600 development-checkpoint records

> ⚠️ **This is a PREVIEW research benchmark.** It is an engineering risk-control
> and research artifact, **not** a clinical assessment, proof of safety, or
> evidence that a system improves human well-being. Automated results produced
> with these scenarios must never be represented as validated human-impact or
> psychological-safety certification.

## Configurations

| Config | Splits | Scenarios | Maturity |
|--------|--------|-----------|----------|
| `v0.1` | `en`, `vi` | 8 + 8 | Research seed |
| `v0.2` | `en`, `vi` | 8 + 8 | Draft research track |
| `v0.3` | `en` | 200 | `maintainer_reviewed` |
| `v0.4` | `en` | 56 | `maintainer_reviewed` |
| `v0.5` | `en` (`en-US`, `en-VN`) | 400 | `maintainer_reviewed`; development only |
| `v0.6` | `en`, `vi` | 800 + 400 | `maintainer_reviewed`; development only |

```python
from datasets import load_dataset

# English v0.3 expansion (200 scenarios)
ds = load_dataset("lamduong/human-ai-impact-bench-scenarios", "v0.3", split="en")

# English v0.4 authored expansion (56 scenarios)
v04 = load_dataset("lamduong/human-ai-impact-bench-scenarios", "v0.4", split="en")

# Stateful-personalization development checkpoint (400 scenarios)
v05 = load_dataset("lamduong/human-ai-impact-bench-scenarios", "v0.5", split="en")

# Balanced legacy-category development checkpoint
v06_en = load_dataset("lamduong/human-ai-impact-bench-scenarios", "v0.6", split="en")
v06_vi = load_dataset("lamduong/human-ai-impact-bench-scenarios", "v0.6", split="vi")

# Bilingual v0.1
en = load_dataset("lamduong/human-ai-impact-bench-scenarios", "v0.1", split="en")
vi = load_dataset("lamduong/human-ai-impact-bench-scenarios", "v0.1", split="vi")
```

## Record schema

Each scenario is a JSON object with these fields (see
[`schemas/scenario.schema.json`](https://github.com/lamduong0/human-ai-impact-bench/blob/main/schemas/scenario.schema.json)):

| Field | Type | Description |
|-------|------|-------------|
| `benchmark_version` | string | `0.1` through `0.6` |
| `scenario_id` | string | Stable kebab-case identifier |
| `language` | string | `en` \| `vi` |
| `title` | string | Short human-readable title |
| `category` | string | e.g. `dependency_boundaries`, `reality_testing`, `engagement_manipulation`, `identity_and_dignity_harm` (24 published categories) |
| `risk_level` | string | `low` \| `moderate` \| `high` \| `critical` |
| `context` | string | Situation description |
| `persona` | object | Age group, situation, communication style, vulnerability factors |
| `initial_prompt` | string | Opening user turn |
| `follow_up_prompts` | list[string] | Scripted subsequent user turns |
| `expected_behaviors` | list[string] | What a safe assistant should do |
| `failure_modes` | list[string] | Concrete unsafe behaviors to detect |
| `dimensions` | list[string] | Scored rubric dimensions |
| `tags` | list[string] | Free-form labels |

Version 0.5 additionally uses `locale`, `protocol_mode`, `matched_pair_id`, and
optional `prefill_messages` to define its synthetic continuous-versus-recovery
protocol pairs. Version 0.6 retains the legacy 14-field interaction contract.

## Intended use

- Red-teaming and pre-release evaluation of chatbots / conversational agents.
- Comparing candidate models on human-impact dimensions.
- Prioritizing scenarios for human review.

**Out of scope:** clinical or psychological safety claims, production sign-off,
or any representation of automated scores as validated human outcomes.

## Review maturity and exclusions

The v0.3 and v0.4 English-first expansions are `maintainer_reviewed`.
Per-scenario review state is published in each revision's
`review-status.json`; neither revision claims independent cultural validation.
Automated benchmark results remain **PREVIEW** evidence.

All 200 v0.3 scenarios were reviewed on 2026-07-28 by maintainer `lamduong0`
for `en-US` and `en-VN`. The reviewer self-reported qualification as software
engineer and disclosed an author/maintainer conflict. The maintainer elected to
skip a second independent reviewer and will steward the dataset. Zero v0.3
items are `culturally_reviewed` or `release_ready`.

All 56 published v0.4 scenarios were reviewed on 2026-07-28 by maintainer
`lamduong0` for `en-US` and `en-VN`. The reviewer self-reported qualification
as software engineer and disclosed an author/maintainer conflict. A second
independent reviewer was intentionally skipped and the maintainer will steward
the dataset. Zero items are `culturally_reviewed` or `release_ready`, and no
specialist safety approval is claimed. Availability in this dataset does not
mean approval for production.

All 400 v0.5 records were reviewed on 2026-07-28 by maintainer `lamduong0` for
`en-US` and `en-VN`. The reviewer self-reported qualification as software
engineer, disclosed an author/maintainer conflict, and elected to skip a second
independent reviewer. They are `maintainer_reviewed`, not independently
`culturally_reviewed`, specialist-approved, or `release_ready`.

All 1,200 v0.6 records were reviewed on 2026-07-29 by maintainer `lamduong0`.
The English records were reviewed for `en-US` and `en-VN`; the Vietnamese
records were reviewed for `vi-VN`. The reviewer self-reported qualification as
software engineer, disclosed an author/maintainer conflict, and elected to
skip a second independent reviewer. They are `maintainer_reviewed`, not
independently `culturally_reviewed`, specialist-approved, or `release_ready`.

The repository also contains 22 sensitive v0.4 drafts awaiting dedicated
safety review. They are intentionally excluded from this dataset and from the
288-record released total. The published v0.5 and v0.6 configurations are
development checkpoints and do not increase that released total.

## Distinctive evaluation design

- Scripted multi-turn probes test behavior under escalating user pressure.
- Scoring covers emotion, autonomy, cognition, trust, social connection, and
  healthy AI–human boundaries rather than emotional recognition alone.
- The companion tooling evaluates a deployed chatbot configuration and records
  dataset, candidate, transcript, judge, and policy provenance.
- Named critical failures can block deployment regardless of a high average
  score.
- The deterministic gate emits separate evidence maturity, decision, and
  deployment action fields for fail-closed CI integration.

This dataset complements conventional content-safety, jailbreak, factuality,
privacy, and bias benchmarks. It does not replace them.

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
user data. Vietnamese v0.6 scenarios are culturally adapted drafts requiring
qualified review; no cultural-validity claim is made. The v0.3-v0.5
maintainer-reviewed expansions are not independently culturally validated or
specialist safety-approved. See the repo's cultural-review guide. Automated
judging can miss nuance and systematically over-score responses — a pass means
only that a captured candidate satisfied the configured automated policy.
