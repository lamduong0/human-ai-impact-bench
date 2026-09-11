# Cultural review guide

## Purpose

HumanAI-Impact-Bench separates scenario drafting from cultural review. A model,
translator, or scenario author may create a draft, but only documented human
review can move an item to `culturally_reviewed` or `release_ready`.

The English-first v0.3 expansion contains 200 template-derived records across
25 concepts and 8 contexts. The English-first v0.4 expansion adds 56 authored
records across 7 categories. Every record in both expansions begins as
`draft_unreviewed`. The contexts increase coverage for review; they are not
evidence that the scenario represents every person in that setting.

## Historical status definitions (v0.1–v0.6)

| Status | Meaning |
|---|---|
| `draft_unreviewed` | Structurally valid draft with no completed cultural review |
| `in_review` | Assigned to reviewers; no approval claim |
| `changes_requested` | Review identified a problem requiring revision |
| `maintainer_reviewed` | Maintainer completed review for named locales; no independent cultural-validation or specialist-safety claim |
| `culturally_reviewed` | Two qualified reviewers completed and documented review for at least one locale |
| `release_ready` | Cultural review is complete and all research, safety, and technical checks are resolved |

The manifest validator requires a named reviewer and reviewed locale for
`maintainer_reviewed`. It requires at least two named reviewer identifiers and
one reviewed locale before accepting `culturally_reviewed` or `release_ready`.
Reviewer identifiers may be pseudonymous in the public repository if project
maintainers retain an auditable confidential mapping.

## v0.7 digest-bound review protocol

All four v0.7 manifests currently mark their 3,400 records `draft_unreviewed`:
2,800 English and 600 non-blocking Vietnamese previews. These are
model-assisted drafts, not human-reviewed adaptations. Neither an English
source's older review status nor automated proofreading supplies approval for
the new target digest or locale.

v0.7 uses `draft_unreviewed`, `in_review`, `changes_requested`, `reviewed`, and
`release_ready`; it does not reuse historical `maintainer_reviewed` or
`culturally_reviewed` labels. Events must bind the exact scenario digest,
review type, reviewer, qualification, locale, conflict disclosure and decision.
Qualifying approvals need explicit author identities so independence is
auditable; absent author IDs cannot be replaced by an invented identity or a
free-text assertion of no conflict. Actual declarations may be added when the
responsible humans provide them. Distinct reviewers' decisions are preserved;
one later approval must not erase another reviewer's unresolved change request.

Independent construct review is required. Vietnamese additionally needs
`vi-VN` locale review; high/critical risk or `requires-specialist-review`
items require specialist-safety review. A release decision is separate from
these checks and is not a deployment approval. Changing text makes its prior
digest approval stale; update the source JSONL, review manifest, exact lineage
and coverage artifacts together. For v0.7 the JSONL is the authored source of
truth, not a scenario generator.

```bash
PYTHONPATH=src python scripts/generate_v07_review_manifests.py
PYTHONPATH=src python scripts/validate_cultural_review.py \
  --scenarios data/scenarios/v0.7/core/vi \
  --manifest data/scenarios/v0.7/core/vi/review-status.json
```

Run the same validation separately for the other three track/language
directories. Review matched agentic common prompts/rubrics together while
checking every translated prefill and member-specific source binding. Confirm
that consent, uncertainty, evidence and practical access constraints remain
aligned, not merely grammatically fluent. Do not infer cultural equivalence
from exact IDs or risk/dimension matching. No quantitative evidence verifier
currently promotes above `REVIEWED_DATASET`, and no v0.7 policy permits ALLOW.

## Reviewer qualifications

Each scenario should receive:

1. Review from a fluent speaker familiar with the target locale and pragmatic
   use of the language.
2. Independent review from a person with relevant HCI, safety, behavioral
   research, or domain expertise.
3. Adjudication when reviewers disagree about risk, interpretation, or expected
   behavior.

Reviewers should disclose relevant conflicts, model-provider relationships,
and whether they helped author the scenario. At least one reviewer should be
independent of the original author.

## Review checklist

For every scenario, reviewers should answer:

- Does the scenario test the stated construct rather than a stereotype?
- Is the persona context plausible without implying that demographic or
  cultural identity is itself a vulnerability?
- Would the wording be understood naturally in the reviewed locale?
- Are relationship distance, politeness, disagreement, family roles, and
  help-seeking expectations represented appropriately?
- Are proposed verification and support options feasible and safe?
- Are expected behaviors observable without prescribing one culturally narrow
  response?
- Do failure modes identify harmful model behavior without diagnosing the
  scripted user?
- Could the prompt itself create unnecessary harm, teach abuse, or expose
  sensitive personal information?
- Does the item duplicate another scenario without adding meaningful context?
- Are dimensions, risk level, and critical failures calibrated consistently
  with comparable items?

Record concrete notes and requested edits. Do not approve an item solely because
it is grammatically fluent.

## Workflow

1. Regenerate the deterministic draft corpus or review manifest when source
   scenarios change:

   ```bash
   python3 scripts/generate_v03_english_scenarios.py
   PYTHONPATH=src python3 scripts/generate_v04_review_manifest.py
   ```

2. Validate the scenario file:

   ```bash
   PYTHONPATH=src python3 -m humanai_impact_bench.cli validate \
     data/scenarios/v0.3/en.jsonl
   PYTHONPATH=src python3 -m humanai_impact_bench.cli validate \
     data/scenarios/v0.4
   ```

3. Assign reviewers by editing the matching `review-status.json` under v0.3 or
   v0.4.
4. Review the scenario independently and record notes before reconciliation.
5. Apply requested scenario changes to the generator, not only the generated
   JSONL, then regenerate.
6. Update manifest status, reviewers, reviewed locales, and notes.
7. Validate review claims:

   ```bash
   PYTHONPATH=src python3 scripts/validate_cultural_review.py \
     --scenarios data/scenarios/v0.3/en.jsonl \
     --manifest data/scenarios/v0.3/review-status.json
   PYTHONPATH=src python3 scripts/validate_cultural_review.py \
     --scenarios data/scenarios/v0.4 \
     --manifest data/scenarios/v0.4/review-status.json
   ```

8. Run tests and inspect the generated diff before publication.

## English-first scope

English priority means concept development starts in English. It does not mean
English is culturally neutral or universally transferable. Record the locale
actually reviewed, such as `en-US`, `en-GB`, `en-IN`, `en-SG`, or another
specific context. Do not mark a scenario as reviewed for all English speakers
based on one locale.

Future languages should adapt the construct and situation with native reviewers
rather than translate the English sentence mechanically. Cross-language score
comparisons require separate evidence of measurement equivalence.

## Release reporting

Publish:

- counts by status, concept, risk, context, and reviewed locale;
- reviewer qualifications and independence;
- adjudication procedure and major revisions;
- unresolved limitations and excluded scenarios;
- machine-generation or templating disclosure;
- the exact dataset, manifest, and code revision.

Until every released item meets the review policy, describe v0.3 and v0.4 as
English-first DRAFT expansions, not culturally validated benchmark releases.
