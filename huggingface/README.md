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
- **Repository snapshot:** 5,288 physical records across ten configurations:
  1,888 historical records plus 3,400 v0.7 drafts. The released total remains
  288; the other 5,000 records are development data.
- **v0.7 snapshot:** 3,400 model-assisted draft records in four separate
  configurations; publication does not change their review or evidence status.
- **Tested source/tooling revision:**
  [`07005c3`](https://github.com/lamduong0/human-ai-impact-bench/tree/07005c3b0bc51666cce95ff78f29f403232bcd67).

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
| `v0.6` | `en`, `vi` | 800 + 400 | 210 `maintainer_reviewed`, 990 `draft_unreviewed`; development only |
| `v0.7-core-en` | `en` | 2,400 | `draft_unreviewed`; primary English |
| `v0.7-agentic-en` | `en` | 400 (200 pairs) | `draft_unreviewed`; primary English |
| `v0.7-core-vi-preview` | `vi` | 400 | `draft_unreviewed`; non-blocking preview |
| `v0.7-agentic-vi-preview` | `vi` | 200 (100 pairs) | `draft_unreviewed`; non-blocking preview |

The v0.7 primary English milestone has 2,800 records; the two Vietnamese
previews add 600. Each configuration routes only to its named track/language
directory. Validate and score configurations separately; never pool core and
agentic tracks or interpret translation pairs as independent concepts.
The current counts and draft status reconcile with the repository's
`data/scenarios/v0.7/configuration-index.json`, including exact JSONL paths and
hashes, four review manifests and resolved overlap audit. Publishing these
artifacts does not constitute human review, empirical validation or a package release.

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
[`schemas/scenario.schema.json`](https://github.com/lamduong0/human-ai-impact-bench/blob/07005c3b0bc51666cce95ff78f29f403232bcd67/schemas/scenario.schema.json)):

| Field | Type | Description |
|-------|------|-------------|
| `benchmark_version` | string | `0.1` through `0.7` |
| `benchmark_track` | string | Required for v0.7: `core` or `agentic` |
| `scenario_id` | string | Stable kebab-case identifier |
| `language` | string | `en` \| `vi` |
| `title` | string | Short human-readable title |
| `category` | string | v0.7 has 24 core categories and four separately registered agentic categories |
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
Version 0.7 agentic uses `locale`, `protocol_mode` (`control` or
`prefill_stress`), `matched_pair_id`, and stress-only `prefill_messages`.
Each pair holds visible prompts, metadata and the common rubric fixed; only
synthetic prior history differs. Score newly generated candidate replies, not
benchmark-authored assistant prefills. Action probes concern conversational
authorization claims, not observed tool execution, and simulated session
history does not verify product memory.

## Intended use

- Red-teaming and pre-release evaluation of chatbots / conversational agents.
- Comparing candidate models on human-impact dimensions.
- Prioritizing scenarios for human review.

**Out of scope:** clinical or psychological safety claims, production sign-off,
or any representation of automated scores as validated human outcomes.

## Review maturity and exclusions

All 3,400 v0.7 records are model-assisted `draft_unreviewed`, with empty review
events and no inherited source approvals. Vietnamese adaptation preserves
selected English source lineage but still requires native-speaker/cultural
and applicable specialist review; source matching is not cultural equivalence.
Public calibration/evaluation splits are both public and therefore not blind.
Any blind-set claim requires separately access-controlled data and a verified
pre-evaluation commitment, not merely the public split name.

No v0.7 deployment policy exists. Automated evaluation remains PREVIEW; the
generic gate returns `REVIEW_REQUIRED`/`HOLD` for otherwise passing v0.7 runs.
Quantitative evidence verification is not implemented: the evidence-status
tool cannot promote beyond `REVIEWED_DATASET`, and these unreviewed drafts do
not meet even that stage. Hashes, declarations and record counts are not
validated evaluation, clinical safety or human-outcome evidence.

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

This v0.7 upload preserves the previously published v0.6 review manifests:
210 English records are `maintainer_reviewed`; 590 English and all 400
Vietnamese records remain `draft_unreviewed`. Later v0.6 review updates in
the GitHub checkout are not applied by this upload. `PUBLICATION.json` records
the preserved Hugging Face revision and the three historical metadata files
that differ from the source checkout. No independent cultural or specialist
approval, or `release_ready` status, is implied.

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
[deployment-gate docs](https://github.com/lamduong0/human-ai-impact-bench/blob/07005c3b0bc51666cce95ff78f29f403232bcd67/docs/deployment-gate.md).

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
