# Dataset history and review status

[Project overview](../README.md) · [Historical results](results/README.md)

Dataset versions are separate from Python package versions. Counts are physical
records across versioned configurations; they are not independent concepts.
The v0.1–v0.7 descriptions below preserve the repository's recorded coverage and
review history. Hosted historical metadata can differ from the checkout; the
[Hugging Face card](../huggingface/README.md) documents those differences.

## v0.8 development snapshot

The English-only v0.8 corpus contains 2,400 core and 400 agentic records, all
`draft_unreviewed`. Its 64-record pilot and 192 synthetic diagnostic transcripts
support automated evaluation development. Diagnostics are not extra scenarios.
Across v0.1–v0.8, the checkout contains 8,088 physical scenario records; the
historical released total remains 288. v0.8 has not been uploaded to Hugging Face
by this work. See the [configuration index](../data/scenarios/v0.8/configuration-index.json),
[evaluation guide](v0.8-evaluation-guide.md), and [evidence status](v0.8-results-status.md).

## v0.1–v0.7 repository snapshot

| Dataset | Languages | Records | Coverage | Current status |
|---|---|---:|---|---|
| v0.1 seed set | English, Vietnamese | 16 | 8 aligned multi-turn scenarios | Research seed |
| v0.2 reality-testing track | English, Vietnamese | 16 | 8 aligned multi-turn concepts | Draft research track |
| v0.3 English expansion | English | 200 | 25 concepts × 8 contexts | `maintainer_reviewed` |
| v0.4 authored expansion | English | 56 | 7 categories × 8 scenarios | `maintainer_reviewed` |
| v0.5 stateful-personalization checkpoint | English (`en-US`, `en-VN`) | 400 | 8 categories × 25 matched protocol pairs; mature target: 800 | `maintainer_reviewed`; development only |
| v0.6 balanced legacy-category checkpoint | English, Vietnamese | 1,200 | 24 categories × 50 physical records; 400 aligned EN/VI pairs across 16 categories | `maintainer_reviewed`; development only |
| `v0.7-core-en` | English | 2,400 | 24 categories × 25 families × 4 contexts | `draft_unreviewed`; primary English |
| `v0.7-agentic-en` | English | 400 | 4 categories × 25 families × 2 contexts × 2 modes | `draft_unreviewed`; primary English |
| `v0.7-core-vi-preview` | Vietnamese | 400 | 16 categories × 25 families × 1 selected context | `draft_unreviewed`; non-blocking preview |
| `v0.7-agentic-vi-preview` | Vietnamese | 200 | 4 categories × 25 families × 1 selected context × 2 modes | `draft_unreviewed`; non-blocking preview |
| **Released total** |  | **288** | v0.1–v0.4 |  |
| **Historical subtotal** |  | **1,888** | v0.1–v0.6 physical records |  |
| **v0.1–v0.7 subtotal** |  | **5,288** | Historical 1,888 + draft v0.7 3,400 |  |

The v0.3 corpus is template-derived and the v0.4 corpus is authored
English-first. Both have completed one disclosed maintainer review and are
`maintainer_reviewed`; neither claims independent cultural validation. Their
per-scenario status is tracked in review manifests. Dataset maturity is
separate from automated benchmark evidence: automated evaluations remain
**PREVIEW** regardless of corpus size.

All 200 v0.3 scenarios were reviewed on 2026-07-28 by maintainer `lamduong0`
for `en-US` and `en-VN`. The reviewer self-reported qualification as software
engineer and disclosed an author/maintainer conflict. The maintainer elected to
skip a second independent reviewer and will steward the dataset. Zero v0.3
items are `culturally_reviewed` or `release_ready`.

All 56 published v0.4 scenarios were reviewed on 2026-07-28 by maintainer
`lamduong0` for `en-US` and `en-VN`. The reviewer self-reported qualification
as software engineer and disclosed an author/maintainer conflict. A second
independent reviewer was intentionally skipped and the maintainer will steward
the dataset. All 56 items are `maintainer_reviewed`; zero are
`culturally_reviewed` or `release_ready`, and no specialist safety approval is
claimed. “Published” means openly available for research and PREVIEW
engineering evaluation; it does not mean independently culturally validated or
approved for production deployment.

The 22 sensitive v0.4 drafts under
[`data/scenarios/pending-safety-review`](../data/scenarios/pending-safety-review)
are quarantined and excluded from the 288 public records, deployment gates,
and Hugging Face dataset until their required safety review is complete.

All 400 v0.5 records were reviewed on 2026-07-28 by maintainer `lamduong0` for
`en-US` and `en-VN`. The reviewer self-reported qualification as software
engineer, disclosed an author/maintainer conflict, and elected to skip a second
independent reviewer. The records are `maintainer_reviewed`, not independently
`culturally_reviewed`, specialist-approved, or `release_ready`. They remain
excluded from the 288-record released total. They are mirrored to Hugging Face
as a development-only configuration and must not be used to claim production
readiness, persistent-memory behavior, or human outcomes.

All 1,200 v0.6 records were reviewed on 2026-07-29 by maintainer `lamduong0`.
The English records were reviewed for `en-US` and `en-VN`; the Vietnamese
records were reviewed for `vi-VN`. The reviewer self-reported qualification as
software engineer, disclosed an author/maintainer conflict, and elected to
skip a second independent reviewer. All records are `maintainer_reviewed`, not
independently `culturally_reviewed`, specialist-approved, or `release_ready`.
They remain development-only and excluded from the 288-record released total.

All v0.7 records are model-assisted drafts. Their four digest-bound manifests
contain `draft_unreviewed` items with empty review events; neither source
lineage nor automated review supplies human approval. Counts above are checked
against the current JSONLs, draft manifests and
[configuration index](../data/scenarios/v0.7/configuration-index.json). This
locally frozen snapshot binds the reviewed overlap dispositions and current
artifact digests; it is not publication, human approval or a new package release.


## v0.2 reality-testing track

The DRAFT [v0.2 dataset](../data/scenarios/v0.2) adds eight aligned English and
Vietnamese concepts for unusual-belief reinforcement, persecutory
interpretation, hidden messages, false shared memories, assistant-planted
memories, correction, reality testing, and simulated epistemic dependence.

Use the strict
[reality-testing PREVIEW gate](../configs/reality-testing-draft-gate.json) and read
the [research context](v0.2-research-context.md) before interpreting
results. The automated and synthetic-session layers measure model behavior,
not clinical hallucination, delusion, false-memory formation, or long-term
human outcomes. Direct measurement requires a separate ethics-reviewed human
study.


## v0.5 stateful-personalization pilot

The development [v0.5 dataset](../data/scenarios/v0.5) has reached a 400-record
maintainer-reviewed coverage checkpoint and targets an 800-record mature
standard. The checkpoint covers
personalized vulnerability exploitation, memory consent,
cross-session dependency recovery, relationship guidance, cognitive
scaffolding, institutional coercion, emotion inference, and grief or memorial
simulation.

Each of the 200 matched pairs contains a `continuous` control and a
`prefill_recovery` stress member. Prefill messages are synthetic,
benchmark-owned context; they were not generated by the tested model and do
not reproduce or verify a provider's persistent-memory system. Read the
[research plan](v0.5-research-plan.md) and
[category proposal](v0.5-category-proposal.md) before using this draft.
All automated results remain PREVIEW transcript evidence.
The staged construct and review requirements are defined in the
[scenario coverage standard](scenario-coverage-standard.md).


## v0.6 balanced legacy-category expansion

The [v0.6 dataset](../data/scenarios/v0.6) now reaches its first complete
authoring checkpoint: 50 physical records for each of all 24 populated legacy
categories. Sixteen categories contain 25 aligned English–Vietnamese concept
pairs; eight English-first categories contain 50 English records, for 800
English and 400 Vietnamese records overall.

The [checkpoint index](../data/scenarios/v0.6/checkpoint-index.json) freezes all
1,200 scenario digests. The
[lineage index](../data/scenarios/v0.6/lineage-index.json) records 90
source-preserving adaptations and 1,110 newly authored records. The
[English](../data/scenarios/v0.6/en/review-status.json) and
[Vietnamese](../data/scenarios/v0.6/vi/review-status.json) review manifests bind
the disclosed full-checkpoint maintainer review to every scenario digest.
This status does not imply independent cultural validation, specialist safety
approval, or release readiness.

Load the two v0.6 language splits from the
[Hugging Face dataset](https://huggingface.co/datasets/lamduong/human-ai-impact-bench-scenarios):

```python
from datasets import load_dataset

v06_en = load_dataset(
    "lamduong/human-ai-impact-bench-scenarios", "v0.6", split="en"
)
v06_vi = load_dataset(
    "lamduong/human-ai-impact-bench-scenarios", "v0.6", split="vi"
)
```

Or validate the repository copies directly. The language directories are
validated separately because v0.6 stores its JSONL files below `en/` and `vi/`:

```bash
PYTHONPATH=src python -m humanai_impact_bench.cli validate data/scenarios/v0.6/en
PYTHONPATH=src python -m humanai_impact_bench.cli validate data/scenarios/v0.6/vi
```

Read the [v0.6 coverage plan](v0.6-legacy-coverage-plan.md) before using
the development data. Structural bilingual alignment, exact duplicate checks,
and the digest-bound
[English](../data/scenarios/v0.6/checkpoint-lexical-similarity-audit-en.json) and
[Vietnamese](../data/scenarios/v0.6/checkpoint-lexical-similarity-audit-vi.json)
lexical screens supplement—but do not replace—human semantic, construct,
locale, and safety review. The
[full-checkpoint review record](v0.6-checkpoint-review.md) documents the
review scope and limitations; the earlier
[Stage 1 review record](v0.6-stage1-review.md) remains as historical
provenance for the frozen 210-record foundation.


## v0.7 English core and agentic drafts

Keep these four configurations separate for validation, execution and scoring:

```bash
PYTHONPATH=src python -m humanai_impact_bench.cli validate data/scenarios/v0.7/core/en
PYTHONPATH=src python -m humanai_impact_bench.cli validate data/scenarios/v0.7/agentic/en
PYTHONPATH=src python -m humanai_impact_bench.cli validate data/scenarios/v0.7/core/vi
PYTHONPATH=src python -m humanai_impact_bench.cli validate data/scenarios/v0.7/agentic/vi
```

The [Hugging Face card](../huggingface/README.md) defines exact local routing for
`v0.7-core-en`, `v0.7-agentic-en`, `v0.7-core-vi-preview`, and
`v0.7-agentic-vi-preview`; this metadata change is not an upload confirmation.
English core expands 24 categories to 100 records each. The four agentic
categories cover memory governance, personalized persuasion, delegated action
authorization, and recovery/correction. Their 200 English matched pairs use
identical visible prompts and a common history-conditional rubric, comparing
`control` with `prefill_stress`. Vietnamese selects one English context per
family and includes 100 translated agentic pairs.

Synthetic prefills are benchmark-authored history, not target-generated output
or evidence of real product memory. Score only the candidate's new replies;
recovery requires a concrete correction, not a generic apology or forced
confession. Action cases measure conversational authorization behavior, not
tool execution. Preserve current consent changes and useful, clearly authorized
low-risk preparation. See the [agentic research plan](v0.7-agentic-research-plan.md)
and [annotation guide](annotation-guide.md).

The [lineage](../data/scenarios/v0.7/lineage-index.json) and
[split](../data/scenarios/v0.7/split-index.json) indexes bind sources and keep
concept families together. Physical records and paired translations are not
independent evidence: cluster by concept family, preserve matched contrasts,
and report each track/language separately. Both calibration and
`public_evaluation` are public; neither is a blind set. Verify a separately
access-controlled blind corpus against its prior commitment with
`humanai-impact-bench verify-blind-set --manifest <commitment.json> --scenarios <private-jsonl>`;
this repository does not supply or claim a completed blind evaluation.

No v0.7-specific deployment policy exists. A generic-policy gate remains
`REVIEW_REQUIRED`/`HOLD` even when numerical checks pass. Quantitative evidence
verification is not implemented; evidence-status cannot advance beyond
`REVIEWED_DATASET`, and the current draft manifests do not meet that stage.
All automated runs remain PREVIEW. No cultural equivalence, persistent-memory
performance, real action completion, clinical safety or human outcome is
established by this corpus.
