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
  - config_name: v0.7-core-en
    data_files:
      - split: en
        path: data/scenarios/v0.7/core/en/*.jsonl
  - config_name: v0.7-agentic-en
    data_files:
      - split: en
        path: data/scenarios/v0.7/agentic/en/*.jsonl
  - config_name: v0.7-core-vi-preview
    data_files:
      - split: vi
        path: data/scenarios/v0.7/core/vi/*.jsonl
  - config_name: v0.7-agentic-vi-preview
    data_files:
      - split: vi
        path: data/scenarios/v0.7/agentic/vi/*.jsonl
  - config_name: v0.8-core-en
    data_files:
      - split: en
        path: data/scenarios/v0.8/core/en/*.jsonl
  - config_name: v0.8-agentic-en
    data_files:
      - split: en
        path: data/scenarios/v0.8/agentic/en/*.jsonl
dataset_info:
  - config_name: v0.7-core-en
    features: &v07_core_features
      - {name: benchmark_version, dtype: string}
      - {name: benchmark_track, dtype: string}
      - {name: scenario_id, dtype: string}
      - {name: language, dtype: string}
      - {name: title, dtype: string}
      - {name: category, dtype: string}
      - {name: risk_level, dtype: string}
      - {name: context, dtype: string}
      - name: persona
        struct:
          - {name: age_group, dtype: string}
          - {name: situation, dtype: string}
          - {name: communication_style, dtype: string}
          - {name: vulnerability_factors, list: string}
      - {name: initial_prompt, dtype: string}
      - {name: follow_up_prompts, list: string}
      - {name: expected_behaviors, list: string}
      - {name: failure_modes, list: string}
      - {name: dimensions, list: string}
      - {name: tags, list: string}
  - config_name: v0.7-core-vi-preview
    features: *v07_core_features
  - config_name: v0.7-agentic-en
    features: &v07_agentic_features
      - {name: benchmark_version, dtype: string}
      - {name: benchmark_track, dtype: string}
      - {name: scenario_id, dtype: string}
      - {name: language, dtype: string}
      - {name: title, dtype: string}
      - {name: category, dtype: string}
      - {name: risk_level, dtype: string}
      - {name: context, dtype: string}
      - name: persona
        struct:
          - {name: age_group, dtype: string}
          - {name: situation, dtype: string}
          - {name: communication_style, dtype: string}
          - {name: vulnerability_factors, list: string}
      - {name: initial_prompt, dtype: string}
      - {name: follow_up_prompts, list: string}
      - {name: expected_behaviors, list: string}
      - {name: failure_modes, list: string}
      - {name: dimensions, list: string}
      - {name: tags, list: string}
      - {name: locale, dtype: string}
      - {name: matched_pair_id, dtype: string}
      - {name: protocol_mode, dtype: string}
      - name: prefill_messages
        list:
          - {name: role, dtype: string}
          - {name: content, dtype: string}
  - config_name: v0.7-agentic-vi-preview
    features: *v07_agentic_features
  - config_name: v0.8-core-en
    features: *v07_core_features
  - config_name: v0.8-agentic-en
    features: *v07_agentic_features
---

# HumanAI-Impact-Bench — Scenarios

Fictional multi-turn scenarios for evaluating conversational AI behavior related
to **emotion, autonomy, cognition, trust, and social connection**.

> **Hugging Face publication draft:** v0.8 is prepared for upload. Publishing the
> GitHub branch does not publish these HF configurations. Evidence remains **PREVIEW**.

[Code and tooling](https://github.com/lamduong0/human-ai-impact-bench) ·
[Apache-2.0 license](https://github.com/lamduong0/human-ai-impact-bench/blob/main/LICENSE) ·
[Citation](https://github.com/lamduong0/human-ai-impact-bench/blob/main/CITATION.cff)

## v0.8 data

| Configuration | Language | Scenarios | Review status |
|---|---|---:|---|
| `v0.8-core-en` | English | 2,400 across 24 categories | `draft_unreviewed` |
| `v0.8-agentic-en` | English | 400 across 4 categories; 200 matched pairs | `draft_unreviewed` |

The 64-record pilot selects existing scenarios. Its 192 synthetic judge-diagnostic
transcripts are authored hypotheses, not additional scenarios or human gold labels.
Earlier English/Vietnamese configurations and review records are preserved in the
[version history](DATASET_DETAILS.md#historical-configurations).

## Matched comparison: 44 scenarios

Overall scores (0–100), using **GPT-6.1 Sol as judge** on the same completed
scenarios for both models.

| Scope | Scenarios | GPT-6.1 Sol | Claude Opus 5 |
|---|---:|---:|---:|
| Core calibration | 16 | 99.64 | 79.77 |
| Core public evaluation | 17 | 97.87 | 65.08 |
| Agentic calibration | 5 | 100.00 | 88.89 |
| Agentic public evaluation | 6 | 100.00 | 91.21 |

**PREVIEW:** Sol also judges itself; output caps were 4,096 / 1,024 tokens.
The 20 failed Opus scenarios are excluded. Results vary substantially by judge;
see [comparison details](DATASET_DETAILS.md#matched-44-comparison).

## Load data

Load a published configuration:

```python
from datasets import load_dataset

core = load_dataset(
    "lamduong/human-ai-impact-bench-scenarios", "v0.7-core-en", split="en"
)
```

For the local v0.8 draft, use the [local loading instructions](DATASET_DETAILS.md#load-the-local-v08-draft).
Use the v0.8 names with the remote dataset ID only after upload and remote loading
have been verified. Pin the dataset revision for reproducible evaluation.

## Record format

Each JSONL record includes scenario identity, category/risk, persona/context,
initial and follow-up prompts, expected behaviors, failure modes, and scoring
dimensions. Agentic records add matched control/stress protocols and optional
synthetic prefills. See the [full schema and protocol notes](DATASET_DETAILS.md#record-schema).

## Evidence and limitations

- All v0.7 and v0.8 scenarios are model-assisted, unreviewed drafts. Earlier
  maintainer review does not establish independent cultural or specialist validation.
- Score candidate-generated replies only. Synthetic history does not verify
  real product memory or tool execution.
- Keep tracks, languages and evaluation subsets separate. Public subsets are
  not blind tests, and related records are not independent observations.
- Automated scores do not establish human outcomes, clinical safety or production
  readiness. Incomplete runs do not support a model ranking; v0.8 remains `HOLD`.
- Scenarios represent fictional adults. Quarantined sensitive drafts remain
  excluded from the published configurations.

See [review history and exclusions](DATASET_DETAILS.md#review-maturity-and-exclusions)
for the detailed evidence boundaries and preserved historical metadata.
