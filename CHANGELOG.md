# Changelog

This file records changes to the `human-ai-impact-bench` Python distribution.
Scenario-dataset revisions (v0.1, v0.2, …) are versioned separately and
documented in the [README](README.md); a dataset revision does not imply a
package release.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [semantic versioning](https://semver.org/) with the
pre-1.0 convention that a minor bump may change a public interface.

## [0.2.0] - Unreleased

Makes the scope and measurement support of a benchmark score explicit. Nothing
here changes how a candidate is scored; it changes what a report is required
to disclose about the score it publishes.

### Added

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
- The benchmark card lists all 13 dimensions and all 14 critical failures; it
  previously listed only the 9 v0.1 dimensions and 6 v0.1 critical failures.

### Notes for upgraders

- `score` and `draft-evaluate` JSON gains keys. Consumers that assert an exact
  key set need updating; consumers that read named keys do not.
- `BenchmarkResult` gains fields. Constructing it positionally will break;
  keyword construction is unaffected.
- Reports produced by 0.1.0 remain evaluable. They fail only against a policy
  that opts in to `minimum_annotations_per_dimension`, which is the intended
  fail-closed behavior.

## [0.1.0] - 2026-07-23

Initial release: scenario validation, provider-neutral annotation scoring, an
OpenAI-compatible runner, a separate automated PREVIEW judge, and a
fail-closed deployment gate with provenance binding.
