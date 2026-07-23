---
name: humanai-impact-bench
description: Run, compare, interpret, and extend HumanAI-Impact-Bench deployment gates for conversational AI. Use when an agent needs to benchmark an OpenAI-compatible chatbot, compare candidate models with controlled evaluation settings, inspect human-impact failures, add bilingual scenarios or policies, or develop the v0.2 delusion-reinforcement, false-memory, reality-testing, and longitudinal-impact research track.
---

# HumanAI-Impact-Bench

Work from the repository root. Preserve the visible project name
`HumanAI-Impact-Bench`; use the normalized CLI and package names already defined
by the repository.

## Choose the workflow

- For a deployment dry run, validate inputs, run target conversations, produce
  DRAFT annotations, then apply the deterministic gate.
- For a model comparison, hold the dataset, system prompt, judge, judge settings,
  and policy constant. Record each target's actual generation settings.
- For scenario development, preserve EN/VI concept parity and validate both
  files before scoring.
- For v0.2 reality-testing research, read
  [references/v0.2-research-plan.md](references/v0.2-research-plan.md) before
  changing scenarios, schemas, metrics, or claims.

## Run a deployment gate

1. Inspect `README.md`, `docs/deployment-gate.md`, the selected scenario source,
   and the policy.
2. Validate scenarios:

   ```bash
   PYTHONPATH=src python3 -m humanai_impact_bench.cli validate data/scenarios/v0.1
   ```

3. Keep credentials only in an environment variable named by
   `--target-api-key-env` or `--judge-api-key-env`. Never place a token in Git,
   artifacts, command output, or a committed environment file. Treat a token
   pasted into chat as exposed and request rotation.
4. Run the target with the deployed system prompt and actual generation
   settings. Use `--omit-temperature` only when the provider rejects an explicit
   value.
5. Run `draft-evaluate` with an independent, fixed judge when possible. Use
   `--omit-judge-temperature` or `--omit-response-format` only for confirmed
   provider compatibility.
6. Apply `configs/draft-gate.json`. Preserve `PASS`, `FAIL`, or `BLOCK` exactly.
7. Save local transcripts under `.local-runs/`; do not commit them by default.

## Compare models

Use one judge and one policy for every candidate. Report:

- target model and exact configuration;
- scenario, language, and call counts;
- overall, language, and dimension scores;
- critical failures and gate result;
- lowest-scoring scenarios with evidence;
- provenance limitations.

Do not compare scores produced by different judges as if they were controlled.
If a hosted alias lacks an immutable weight or deployment digest, label a
configuration hash as non-release-grade provenance.

## Extend the benchmark

Keep each scenario focused on one primary failure mechanism. Add the same concept
in English and Vietnamese with aligned intent, risk, expected behaviors, failure
modes, and dimensions. Do not assume literal translations have equivalent
cultural meaning; request native-speaker review.

Separate three evidence layers:

1. Chatbot behavior under controlled prompts.
2. Simulated multi-session proxy behavior.
3. Longitudinal human outcomes.

Never claim that layers 1 or 2 directly establish psychological harm, clinical
safety, hallucination incidence, or causal long-term effects.

## Validate changes

Run:

```bash
PYTHONPATH=src pytest -q
ruff check .
ruff format --check .
python3 /path/to/skill-creator/scripts/quick_validate.py skills/humanai-impact-bench
```

Also run `git diff --check` and scan generated artifacts for credential patterns
before sharing or publishing them.
