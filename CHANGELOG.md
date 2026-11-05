# Changelog

This file records changes to the `human-ai-impact-bench` Python distribution.
Scenario-dataset revisions (v0.1, v0.2, …) are versioned separately and
documented in the [README](README.md); a dataset revision does not imply a
package release.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [semantic versioning](https://semver.org/) with the
pre-1.0 convention that a minor bump may change a public interface.

## [0.2.0] - Unreleased

Makes score scope and measurement support explicit, adds draft v0.7 dataset
support, and hardens provenance/review checks. This entry remains unreleased;
the dataset revision does not create a new Python distribution version.

### Added

- English-only v0.8 development configurations with 2,400 core and 400 agentic
  draft scenarios, inherited family splits, immutable lineage and a 64-record pilot.
- Structural and opt-in semantic audits, 192 authored synthetic judge diagnostics,
  bounded study execution, raw-response capture, resumable attempt ledgers,
  per-judge consistency reports and artifact/metric verification. Automated
  evidence stays PREVIEW/HOLD; live inference and publication are separate.

- Four locally prepared v0.7 dataset configurations: `v0.7-core-en` (2,400),
  `v0.7-agentic-en` (400), `v0.7-core-vi-preview` (400), and
  `v0.7-agentic-vi-preview` (200). All 3,400 records are model-assisted drafts;
  the historical 1,888 and released 288-record totals are unchanged.
- Digest-bound draft manifests, same-track translation lineage, family-level
  splits, blind-set commitment verification and exact Hugging Face routing
  tests. The locally frozen configuration index binds the current corpus,
  review manifests and resolved overlap audit; no upload, package release or
  human approval is claimed.
- Provisional `action_authorization_violation` penalty (40.0) and automatic
  safety-failure hook for conversational action claims, not tool execution.

- `humanai-impact-bench cluster-diagnostics` reports the intraclass
  correlation, design effect, and effective record count of a report against a
  scenario set. Template-derived corpora expand a few concepts across many
  contexts, so record count overstates independent evidence; interpret
  candidate differences against `effective_records`.
- `BenchmarkResult` and evaluation reports record `dimension_support`, the
  annotation count behind each dimension. A dimension is a mean over only the
  scenarios that requested it, so dimensions within one run rest on different
  amounts of evidence.
- `BenchmarkResult` and evaluation reports record `active_dimension_weight`,
  the divisor used to renormalize the dimension weights actually exercised by
  a scenario set. The weight registry sums to 1.48, not 1, so this divisor is
  what makes two overall scores comparable or not.
- `BenchmarkResult` and evaluation reports record `total_penalty` and
  `penalty_events` next to the existing per-annotation `penalty`. The diluted
  penalty shrinks as a corpus grows; the raw figures do not.
- Deployment policies accept an optional
  `requirements.minimum_annotations_per_dimension`, enforced against every
  dimension named in `thresholds.dimension_scores`. It fails closed: a policy
  that sets it will fail a report that does not record `dimension_support`.
- The three shipped policies declare their own corpus's measurement-support
  floor — 2 for v0.1, 4 for v0.2, 16 for v0.3 — as a disclosure rather than an
  endorsement, with a test pinning each to the released corpus.

### Changed

- The distribution version is single-sourced from
  `humanai_impact_bench.__version__`, so the package and the distribution
  cannot disagree.
- The benchmark card lists all 13 dimensions and all 15 critical failures; it
  previously listed only the 9 v0.1 dimensions and 6 v0.1 critical failures.
- v0.7 reports propagate version/track scope and reject mixed or stripped
  scope. Review/evidence checks bind actual records and independent review
  events; a generic v0.7 gate remains `REVIEW_REQUIRED`/`HOLD`. Quantitative
  evidence verification is not implemented, so maturity cannot exceed
  `REVIEWED_DATASET`; current unreviewed drafts remain below it.

### Notes for upgraders

- `score` and `draft-evaluate` JSON gains keys. Consumers that assert an exact
  key set need updating; consumers that read named keys do not.
- `BenchmarkResult` gains required fields. Direct construction must supply the
  new fields whether arguments are positional or keyword-based; callers using
  `score_annotations` are unaffected.
- Reports produced by 0.1.0 remain evaluable. They fail only against a policy
  that opts in to `minimum_annotations_per_dimension`, which is the intended
  fail-closed behavior.

## [0.1.0] - 2026-07-23

Initial release: scenario validation, provider-neutral annotation scoring, an
OpenAI-compatible runner, a separate automated PREVIEW judge, and a
fail-closed deployment gate with provenance binding.
