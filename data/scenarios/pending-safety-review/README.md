# Pending safety review — sensitive scenario drafts

These are **draft** scenarios for two safety-sensitive categories:

- `self_harm_and_suicide`
- `minor_safety`

## Status: NOT released, NOT gated

The scenarios here are **quarantined**. They are deliberately kept **out** of the
released `data/scenarios/v0.x/` corpus and out of every deployment-gate policy.
Every record is tagged `requires-safety-review`. A test
(`tests/test_pending_safety_review.py`) enforces both the tag and the quarantine
invariant (these categories must not appear under any released
`data/scenarios/v*/` corpus). The machine-readable `review-status.json` covers
all drafts as `draft_unreviewed`; it does not claim human review.

Validate the manifest and its coverage with:

```bash
PYTHONPATH=src python scripts/validate_cultural_review.py \
  --scenarios data/scenarios/pending-safety-review \
  --manifest data/scenarios/pending-safety-review/review-status.json
```

## What these scenarios are — and are not

They are authored **only** as safe-handling / refusal probes: each scenario
measures whether a model responds *safely* — de-escalating, refusing harmful
requests, offering crisis resources, and encouraging trusted adults or
professional help.

They contain **no** self-harm means or methods and **no** sexual content
involving minors. The minor-safety probes present a self-reported minor whom the
model is expected to protect (decline romantic framing, avoid fostering secrecy
or isolation, redirect to trusted adults).

## Before promotion

Do not promote these into a benchmark version or any gate until they have been
reviewed and signed off by qualified **clinical / child-safety reviewers**,
consistent with the process in [`docs/cultural-review-guide.md`](../../../docs/cultural-review-guide.md)
and the guardrails in [`docs/v0.4-category-proposal.md`](../../../docs/v0.4-category-proposal.md).
As with all benchmark output, results remain PREVIEW and are not a clinical or
safety certification.

## Automated pre-review findings

An author self-review plus an independent automated model pass screened the
original 16 drafts and did not flag a prohibited content payload. This was an
automated development check, not independent human, clinical, child-safety, or
cultural sign-off. It led to present-risk checks, a "perfunctory hotline
referral then disengages" failure mode, abuse-disclosure "not your fault"
reassurance, and false-secrecy/coercive-reporting failure modes.

The automated pass also identified coverage gaps. Six additional quarantined
drafts address non-crisis over-refusal, minor × suicide, third-party crisis,
online-exploitation disclosure, and non-US resource localization:
`self-harm-09`–`self-harm-12`, `minor-safety-09`, and `minor-safety-10`. They
bring the set to 12 `self_harm_and_suicide` plus 10 `minor_safety` drafts. All
22 remain `draft_unreviewed`.

The human reviewers must still decide whether `critical` represents policy
severity or only imminent physical danger. The two non-crisis over-refusal
counter-probes are intentionally `low`; every harm-risk probe remains `high` or
`critical`.
