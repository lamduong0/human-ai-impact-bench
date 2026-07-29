# Scenario coverage standard

Drafted: 2026-07-28 · Status: **PLANNED / quality-gated**

> **Claim boundary:** record count measures authored test coverage, not
> real-world prevalence, cultural validity, clinical safety, or human impact.
> Automated benchmark results remain **PREVIEW engineering evidence** at every
> coverage level.

## Mature standard

The mature HumanAI-Impact-Bench target is **100 physical scenario records per
category**.

The machine-readable source for each target and current development stage is
[`configs/scenario-coverage-standard.json`](../configs/scenario-coverage-standard.json).
Changing a current stage or checkpoint requires updating its dataset, review
manifest, tests, and documentation in the same reviewed change.

The record unit depends on the track:

- A matched stateful track such as v0.5 uses 50 independent constructs, each
  represented by one `continuous` record and one `prefill_recovery` record.
- A bilingual legacy track uses 50 culturally adapted concept pairs: one
  English record and one Vietnamese record per concept.
- An English-first unpaired track uses 100 independently motivated records,
  with concepts, contexts, and pressure mechanisms tracked explicitly.

One hundred records is a coverage target, not permission to generate
superficial rewrites. A category does not reach the mature standard unless it
also passes the quality controls below.

## Development checkpoints

Authoring proceeds in bounded checkpoints:

| Level | Records per category | Matched-pair equivalent | Purpose |
|---|---:|---:|---|
| Development foundation | 30 | 15 pairs | Establish the contract and expose category overlap |
| Coverage checkpoint | 50 | 25 pairs | First complete gate-capable draft |
| Candidate expansion | 80 | 40 pairs | Fill documented construct and locale gaps |
| Mature standard | 100 | 50 pairs | Broad reviewed coverage for a stable release candidate |

Matched tracks use even record counts so every record has its paired control or
stress member. No checkpoint may be promoted merely because it reached the
numeric target.

## Required quality controls

Every checkpoint must satisfy all applicable controls:

1. **Construct matrix:** every pair or record maps to a distinct primary
   mechanism, decision point, context, pressure pattern, and expected safe
   behavior.
2. **Pair integrity:** matched members preserve locale, intent, stakes,
   prompts, dimensions, and risk while varying only the declared treatment.
   Deterministic checks enforce the machine-readable invariants; construct
   review confirms that free-text persona details preserve comparable stakes.
3. **Duplicate audit:** the deterministic audit checks exact prompts,
   components, pair invariants, counts, and category completeness. A separate
   documented review checks near-duplicate and semantic overlap within and
   across categories. Matched twins are excluded from duplicate counts.
4. **Template-leakage review:** prompts must not repeatedly name the desired
   benchmark behavior or use a shared follow-up template that makes the answer
   obvious.
5. **Risk calibration:** risk reflects the scenario's stakes and plausible
   failure, not the category's general importance.
6. **Locale coverage:** locale labels describe intended context only.
   Culturally reviewed status requires a qualified human review recorded in
   the manifest.
7. **Scoring coverage:** dimensions and critical failures must follow from
   observable candidate behavior. Context-only prefill content is never scored
   as candidate output.
8. **Review manifest:** new or changed records begin `draft_unreviewed`; status
   promotion is a separate human decision. The manifest binds status to a
   scenario digest so regeneration preserves unchanged reviews and resets
   changed records to draft.
9. **Discrimination check:** a checkpoint should be tested on multiple
   candidates or controlled response variants to find ambiguous or
   non-discriminating records before the next authoring wave.
10. **Reproducibility:** scenario, policy, system-prompt, transcript, candidate,
    and judge provenance remain bound to every reported run.

## v0.5 trajectory

The eight v0.5 categories therefore have these corpus targets:

- coverage checkpoint: 400 records and 200 matched pairs;
- candidate expansion: 640 records and 320 matched pairs; and
- mature standard: 800 records and 400 matched pairs.

The 50-record checkpoint must be reviewed before authoring the 80-record
checkpoint. The 80-record checkpoint must identify documented residual gaps
before authoring the final 20 records per category.

## Legacy trajectory

Released v0.1-v0.4 artifacts remain immutable. Balanced legacy expansion is
authored under a new benchmark version using the same 100-record mature target.
The v0.6 track has reached its first 50-record checkpoint: 1,200 physical
records across 24 categories. Its frozen 210-record foundation is
`maintainer_reviewed`; the other 990 records remain `draft_unreviewed`.
The construction and lineage rules are defined in
[v0.6-legacy-coverage-plan.md](v0.6-legacy-coverage-plan.md).
