---
name: humanai-impact-bench
description: Run, compare, interpret, and extend HumanAI-Impact-Bench deployment gates and v0.1-v0.7 scenario datasets for conversational AI. Use when benchmarking an OpenAI-compatible chatbot or fine-tune, comparing candidate models with controlled settings, diagnosing PREVIEW human-impact failures, applying or designing a fail-closed policy, developing bilingual or stateful scenarios, reporting measurement support and effective sample size, or researching delusion reinforcement, false memory, reality testing, dependency, and longitudinal human impact.
---

# HumanAI-Impact-Bench

Work from the repository root. Preserve the visible project name
`HumanAI-Impact-Bench`; use the normalized CLI and package names already defined
by the repository.

## Choose the workflow

- For a deployment dry run, validate inputs, run target conversations, produce
  PREVIEW annotations, then apply a policy designed for that dataset revision.
- For a model comparison, hold the dataset, system prompt, judge, judge settings,
  and policy constant. Compare only like-for-like language splits and record
  each target's actual generation settings.
- For v0.5 stateful-personalization work, preserve matched
  `continuous`/`prefill_recovery` pairs and read
  `docs/v0.5-research-plan.md`.
- For v0.6 work, treat `data/scenarios/v0.6/en` (800 records) and
  `data/scenarios/v0.6/vi` (400 records) as separate language sources. Read
  `docs/v0.6-legacy-coverage-plan.md` and the digest-bound review manifests.
- For v0.7 work, use four independent configurations: `v0.7-core-en` (2,400),
  `v0.7-agentic-en` (400), `v0.7-core-vi-preview` (400), and
  `v0.7-agentic-vi-preview` (200). Read `docs/v0.7-agentic-research-plan.md`
  and current source/review artifacts. The 2,800-record primary English and
  600-record non-blocking Vietnamese milestones are all model-assisted drafts,
  not a new package release or an upload claim. Use
  `data/scenarios/v0.7/configuration-index.json` for the locally frozen counts,
  source/review hashes and resolved overlap binding.
- For scenario development, preserve aligned intent rather than literal
  translation, update review and lineage artifacts, and validate every changed
  language source.
- For v0.2 reality-testing research, read
  [references/v0.2-research-plan.md](references/v0.2-research-plan.md) before
  changing scenarios, schemas, metrics, or claims.

## Run a deployment gate

1. Inspect `README.md`, `docs/deployment-gate.md`, the selected scenario source,
   and a policy explicitly designed for that dataset revision. Do not apply the
   v0.1 or v0.3 policy to v0.5, v0.6 or v0.7. No v0.7 deployment policy exists;
   generic-policy numerical success still returns `REVIEW_REQUIRED`/`HOLD`.
2. Validate scenarios:

   ```bash
   PYTHONPATH=src python -m humanai_impact_bench.cli validate data/scenarios/v0.6/en
   PYTHONPATH=src python -m humanai_impact_bench.cli validate data/scenarios/v0.6/vi
   ```

3. Keep credentials only in an environment variable named by
   `--target-api-key-env` or `--judge-api-key-env`. Never place a token in Git,
   artifacts, command output, or a committed environment file. Treat a token
   pasted into chat as exposed and request rotation.
4. Run the target with the deployed system prompt and actual generation
   settings. Probe provider compatibility first. Use `--omit-temperature`,
   `--omit-judge-temperature`, or `--omit-response-format` only when confirmed
   necessary, and hold supported settings constant across candidates.
5. Run `draft-evaluate` with an independent, fixed judge when possible and pass
   the selected policy with `--policy` when it requires a policy digest. Use
   `--judge-retries` for bounded invalid-output or transport retries.
6. Apply the matching policy. If none exists, report PREVIEW scores without a
   gate decision and keep deployment on `HOLD`. Only `PASS` permits `ALLOW`;
   `REVIEW_REQUIRED`, `FAIL`, `BLOCK`, and `ERROR` require `HOLD`.
7. Save local transcripts under `.local-runs/`; do not commit them by default.

Large runs are atomic per `run` invocation: one exhausted timeout, empty
assistant response, or invalid response prevents the split artifact from being
written. Never fabricate placeholder model text or score a partial split.
Prefer deterministic category/file shards for long corpora, record worker
counts, and merge only after verifying complete, non-overlapping identities and
identical provenance. Increasing workers can increase 503s and disconnects; use
bounded concurrency and backoff rather than assuming more workers are faster.

## Compare models

Use one judge and one policy for every candidate. Report:

- target model and exact configuration;
- completed and failed scenario, language, and assistant-turn counts;
- overall, base, language, and dimension scores;
- diluted `penalty`, raw `total_penalty`, and `penalty_events`;
- `dimension_support`, critical failures, safety flag, and gate result;
- cluster ICC, design effect, and effective records when tags encode meaningful
  shared concepts;
- lowest-scoring scenarios with evidence;
- judge independence, alias immutability, and other provenance limitations.

Do not compare scores produced by different judges as if they were controlled.
Do not rank an English-only score against a Vietnamese-only score or publish a
combined score when any required split is missing. Label candidate self-judging
as a bias risk. If a run is incomplete, show verified split-level results and
the exact endpoint failure instead of inferring missing numbers.
If a hosted alias lacks an immutable weight or deployment digest, label a
configuration hash as non-release-grade provenance.

`overall_score` is scoped to the active scenario set and dimension weight
divisor. Do not compare it across dataset revisions or different active
dimension sets. Treat effective-record output as informative only when the
cluster tag groups genuinely related records; one unique cluster per record
makes ICC 0 mechanically uninformative.

## Extend the benchmark

### v0.7 execution and evidence boundaries

Validate each exact track/language directory separately:

```bash
PYTHONPATH=src python -m humanai_impact_bench.cli validate data/scenarios/v0.7/core/en
PYTHONPATH=src python -m humanai_impact_bench.cli validate data/scenarios/v0.7/agentic/en
PYTHONPATH=src python -m humanai_impact_bench.cli validate data/scenarios/v0.7/core/vi
PYTHONPATH=src python -m humanai_impact_bench.cli validate data/scenarios/v0.7/agentic/vi
```

Keep `benchmark_version` and `benchmark_track` on annotations/reports; never
merge core/agentic results or pool English and Vietnamese preview scores.
Preserve concept-family clusters, contexts and control/stress pairs. Physical
records, translated variants and protocol members are not independent concepts.
Both public splits are public. For a separately access-controlled blind set:

```bash
PYTHONPATH=src python -m humanai_impact_bench.cli verify-blind-set \
  --manifest /path/to/prior-commitment.json --scenarios /path/to/private-scenarios.jsonl
```

A commitment verifies integrity, not blind-set quality or empirical validity.
Do not commit private scenarios/transcripts to make this command convenient.

Score newly generated candidate replies only. Synthetic assistant prefills
are benchmark-owned history, not target output or real product memory.
Apply shared rubrics conditionally on available history; never import stress
facts into control or force the target to confess authorship of a prefill.
Recovery needs concrete repair, while action probes measure conversational
permission claims, not actual tools. Honor current explicit consent and permit
clearly authorized low-risk preparation without redundant approval.

Edit v0.7 JSONL source records directly; keep exact source/digest matrices,
lineage, split and review artifacts aligned. Translation lineage may point
only from Vietnamese to English within the same v0.7 track, with explicit
version/language/source tags. A new digest cannot inherit prior approval.
All current review events are empty: model-assisted authoring or automated
review must not invent human identities, independence or cultural/specialist
approval. Read `docs/cultural-review-guide.md` before later review updates.
Quantitative evidence verification is not implemented, so the current tool
cannot advance beyond `REVIEWED_DATASET`; unreviewed drafts remain below it.
Automated results stay PREVIEW and deployment remains HOLD.

### Source development

Keep each scenario focused on one primary failure mechanism. Add the same concept
in English and Vietnamese with aligned intent, risk, expected behaviors, failure
modes, and dimensions. Do not assume literal translations have equivalent
cultural meaning; request native-speaker review.

An English-first expansion may precede language adaptation only when every item
is labeled as an unreviewed draft and covered by a review manifest. For v0.3,
edit `scripts/generate_v03_english_scenarios.py`, regenerate the corpus, and run
`scripts/validate_cultural_review.py`. Never claim that model-generated or
template-derived scenarios are culturally reviewed.

Do not promote `maintainer_reviewed` to `culturally_reviewed`,
specialist-approved, or `release_ready` without the review evidence required by
the repository guides. Keep quarantined sensitive scenarios out of release,
PyPI, gates, and Hugging Face until their specialist review is complete.

Separate three evidence layers:

1. Chatbot behavior under controlled prompts.
2. Simulated multi-session proxy behavior.
3. Longitudinal human outcomes.

Never claim that layers 1 or 2 directly establish psychological harm, clinical
safety, hallucination incidence, or causal long-term effects.

## Validate changes

Run:

```bash
PYTHONPATH=src python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python3 /path/to/skill-creator/scripts/quick_validate.py skills/humanai-impact-bench
```

Also validate every changed scenario source, run `git diff --check`, confirm
`.local-runs/` and quarantined data are not staged, and scan tracked diffs for
credential patterns before sharing or publishing them.
