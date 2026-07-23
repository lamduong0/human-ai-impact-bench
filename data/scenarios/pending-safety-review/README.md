# Pending safety review — sensitive scenario drafts

These are **draft** scenarios for two safety-sensitive categories:

- `self_harm_and_suicide`
- `minor_safety`

## Status: NOT released, NOT gated

The scenarios here are **quarantined**. They are deliberately kept **out** of the
released `data/scenarios/v0.x/` corpus and out of every deployment-gate policy.
Every record is tagged `requires-safety-review`. A test
(`tests/test_pending_safety_review.py`) enforces both the tag and the quarantine
invariant (these categories must not appear under `data/scenarios/v0.4/`).

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
