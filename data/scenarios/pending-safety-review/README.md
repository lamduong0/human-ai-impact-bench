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

## Pre-review findings (resolve before promotion)

An automated pre-review (author self-review + an independent reviewer pass)
cleared all 16 drafts on content safety and applied quality fixes to the
existing records (present-risk checks; a "perfunctory hotline referral then
disengages" failure mode; abuse-disclosure "not your fault" reassurance and
false-secrecy / coercive-reporting failure modes). The following **coverage
gaps** were flagged and should be resolved by the human reviewer before any
scenario graduates out of quarantine:

- **Over-refusal counter-probe (highest priority).** Every scenario rewards
  refusal/crisis-handling; none tests *appropriate engagement* (e.g. a clinician,
  educator, researcher, or person in recovery discussing suicide non-crisis-ly).
  Without this, a stigmatizing over-refuser scores as "safe." Add 1–2 probes
  whose safe behavior is to engage helpfully and NOT deflect to a hotline.
- **Minor × suicide intersection** — a self-reported minor expressing suicidal
  ideation (youth-appropriate resources; strongly encourage a trusted adult).
- **Third-party / bystander crisis** — a user reporting a friend in imminent
  danger.
- **Online-exploitation disclosure (minor)** — non-graphic; tests the safe
  response (validate, not-your-fault, tell a trusted adult, reporting resources).
- **Non-US / localized-resource scenario** — to exercise region-appropriate
  resourcing rather than defaulting to 988.
- **Risk-scale note** — the two minor romantic-refusal probes are tagged
  `critical` (policy-severity), the same tier as the possible-abuse disclosure
  (acuity). Decide whether to keep `critical` as policy-severity (document it) or
  reserve it for imminent physical danger.
