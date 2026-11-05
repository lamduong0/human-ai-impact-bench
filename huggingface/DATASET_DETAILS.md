# HumanAI-Impact-Bench dataset details

[Dataset card](README.md)

This document accompanies the v0.8 Hugging Face publication draft. It preserves detailed
configuration, review and format information. Publish it alongside the card and
matching data when that separate publication is authorized.

## Historical configurations

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
| `v0.8-core-en` | `en` | 2,400 | `draft_unreviewed`; local publication draft |
| `v0.8-agentic-en` | `en` | 400 (200 pairs) | `draft_unreviewed`; local publication draft |

## v0.8 English-only publication draft

The v0.8 corpus preserves the English v0.7 content under new versioned IDs with
explicit source lineage: 2,400 core records across 24 categories and 400 agentic
records across four categories. New IDs do not establish improved scenario
quality. Its 64-record pilot contains 48 core records and 16 agentic records
(eight intact pairs), split equally between calibration and public evaluation.
The pilot selects existing corpus records; it does not add scenario rows or a
Hugging Face configuration. The 192 synthetic diagnostic transcripts are authored
continuations of the 32 calibration pilot records, also not additional scenarios.

All v0.8 records remain `draft_unreviewed`; automated auditing and judge agreement
do not establish human review or accuracy. Diagnostic expectations are authored
hypotheses, not human gold labels. Human review was not performed and is outside
the v0.8 automated evaluation scope. Evidence remains **PREVIEW** and deployment
remains **HOLD**; there is no v0.8 deployment policy. v0.8 adds no Vietnamese
records; earlier bilingual configurations remain available.

The v0.8 configuration index binds exact category files, source lineage, inherited
family splits, the pilot and empty-event review manifests. The Hugging Face split
is `en`; calibration/public-evaluation membership is recorded separately in
`data/scenarios/v0.8/split-index.json`. Both evaluation subsets are public, not
blind. Keep results separate by track, subset, candidate and judge, and disclose
self-judging. Related records, pairs and repeated ratings are not independent
concepts. Configuration and model identifiers do not authenticate provider weights
or prove longitudinal human outcomes.

**Recorded evaluation status (2026-11-05):** the full Sol/Opus pilot is incomplete.
A retrospective comparison of the same 44 completed scenarios is reported below.
It does not turn the original pilot into a complete evaluation or establish
validated human-impact findings.

The development checkout contains `docs/v0.8-evaluation-guide.md`,
`docs/v0.8-results-status.md` and `docs/results/README.md` for execution details
and dated evidence in the development branch. Hugging Face publication remains
a separate step. Structural and loader checks do not establish semantic quality,
hosted dataset availability or human validity.

### Load the local v0.8 draft

Use the development checkout to build a temporary local dataset view. The card
must be named `README.md` beside `data/` for its configuration routes and explicit
nested-list feature types to apply:

```python
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

from datasets import load_dataset

source = Path("/path/to/human-ai-impact-bench").resolve()
with TemporaryDirectory() as temporary:
    bundle = Path(temporary)
    copyfile(source / "huggingface/README.md", bundle / "README.md")
    copyfile(source / "huggingface/DATASET_DETAILS.md", bundle / "DATASET_DETAILS.md")
    (bundle / "data").symlink_to(source / "data", target_is_directory=True)
    cache = str(bundle / "hf-cache")
    core = load_dataset(str(bundle), "v0.8-core-en", split="en", cache_dir=cache)
    agentic = load_dataset(str(bundle), "v0.8-agentic-en", split="en", cache_dir=cache)
    assert len(core) == 2400 and len(agentic) == 400
```

Use the remote dataset ID with these v0.8 names only after a separate upload and
remote loading check confirm the published revision. Pin that revision for a
reproducible study. The source configuration index and hashes identify the local
draft; they are not a Hugging Face revision or a package release.

## Record schema

Each scenario is a JSON object with these fields (see
`schemas/scenario.schema.json` in the corresponding source checkout):

| Field | Type | Description |
|-------|------|-------------|
| `benchmark_version` | string | `0.1` through `0.8` |
| `benchmark_track` | string | Required for v0.7 and v0.8: `core` or `agentic` |
| `scenario_id` | string | Stable kebab-case identifier |
| `language` | string | `en` \| `vi`; v0.8 requires `en` |
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
Versions 0.7 and 0.8 agentic use `locale`, `protocol_mode` (`control` or
`prefill_stress`), `matched_pair_id`, and stress-only `prefill_messages`.
Each pair holds visible prompts, metadata and the common rubric fixed; only
synthetic prior history differs. Score newly generated candidate replies, not
benchmark-authored assistant prefills. Action probes concern conversational
authorization claims, not observed tool execution, and simulated session
history does not verify product memory.

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

## Limitations & ethics

Scenarios intentionally depict vulnerable users (loneliness, grief, crisis,
distorted beliefs). They are fictional probes authored for evaluation, not real
user data. Vietnamese v0.6 scenarios are culturally adapted drafts requiring
qualified review; no cultural-validity claim is made. The v0.3-v0.5
maintainer-reviewed expansions are not independently culturally validated or
specialist safety-approved. See the repo's cultural-review guide. Automated
judging can miss nuance and systematically over-score responses — a pass means
only that a captured candidate satisfied the configured automated policy.

## Matched 44 comparison

The README table reports overall scores for four separate scopes, all using
GPT-6.1 Sol as the common judge. It is the only judge with valid ratings for both
candidates on all 44 scenarios (33 core and 11 agentic). No combined score across
core/agentic or calibration/public-evaluation scopes is defined.

Both models used the same scenario IDs and source contents. Selection occurred
after generation, conditional on Opus completion: 20 failed Opus cases are
excluded. Generation and judging caps differed: Sol 4,096 tokens, Opus 1,024.
Each judge self-evaluates one candidate; neither is independent of both.

### Judge sensitivity on the same 39 scenarios

Opus judging lacks a valid rating for one candidate on five of the 44 scenarios.
The table below holds the remaining 39 scenario IDs fixed for both judges.

| Scope | Scenarios | Sol judge: Sol / Opus | Opus judge: Sol / Opus |
|---|---:|---:|---:|
| Core calibration | 15 | 99.61 / 87.42 | 91.39 / 95.34 |
| Core public evaluation | 14 | 99.40 / 72.95 | 93.96 / 93.45 |
| Agentic calibration | 5 | 100.00 / 88.89 | 96.11 / 100.00 |
| Agentic public evaluation | 5 | 100.00 / 90.94 | 100.00 / 97.46 |

Changing the judge reverses both calibration comparisons and nearly removes the
core public-evaluation gap. These results do not establish an independent model
ranking. Evidence remains PREVIEW and deployment remains HOLD.

The original run verified 3,951 artifacts and remains `comparison_complete=false`.
This offline derivation used saved ratings and sent no new inference requests.
Raw run artifacts, the 44-scenario selection, and per-scenario scores remain local.
