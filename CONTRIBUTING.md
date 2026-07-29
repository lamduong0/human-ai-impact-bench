# Contributing to HumanAI-Impact-Bench

Thank you for helping build a more human-centered AI benchmark.

## Good first contributions

- Review English or Vietnamese scenarios for clarity and cultural validity
- Propose a scenario for an underrepresented failure mode
- Improve annotation anchors with concrete evidence
- Add tests or accessibility improvements
- Reproduce a benchmark result with complete metadata

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
ruff check .
```

## Scenario contributions

A proposed scenario should:

- Test one primary construct and a small number of related dimensions
- Use an adult persona in version `0.1`
- Include at least two follow-up prompts that expose multi-turn behavior
- Describe desired behavior without prescribing one exact sentence
- List observable failure modes
- Avoid real personal data and copyrighted conversation transcripts
- Be reviewed by a fluent speaker for every language version

The mature coverage target is 100 records per category, but contributions must
fill a documented construct or context gap rather than repeat a template.
Authoring advances through quality-gated checkpoints. Read the
[scenario coverage standard](docs/scenario-coverage-standard.md) before
proposing a bulk expansion.

Validate changes with:

```bash
humanai-impact-bench validate data/scenarios/v0.1/en.jsonl
humanai-impact-bench validate data/scenarios/v0.1/vi.jsonl
```

For the English-first v0.3 expansion, edit the concept generator rather than
the generated JSONL directly:

```bash
python3 scripts/generate_v03_english_scenarios.py
humanai-impact-bench validate data/scenarios/v0.3/en.jsonl
PYTHONPATH=src python3 scripts/validate_cultural_review.py \
  --scenarios data/scenarios/v0.3/en.jsonl \
  --manifest data/scenarios/v0.3/review-status.json
```

Do not mark a scenario `culturally_reviewed` or `release_ready` without the
reviewers and locale evidence required by
[docs/cultural-review-guide.md](docs/cultural-review-guide.md).

For a matched v0.5 authoring checkpoint, also run:

```bash
PYTHONPATH=src python scripts/audit_scenario_coverage.py \
  data/scenarios/v0.5 \
  --coverage-config configs/scenario-coverage-standard.json \
  --track v0.5 \
  --matched
PYTHONPATH=src python scripts/generate_v05_review_manifest.py
```

The expected count must match the active checkpoint in
[`configs/scenario-coverage-standard.json`](configs/scenario-coverage-standard.json).
This command performs deterministic exact checks. A documented semantic
near-duplicate and template-leakage review is also required before promoting a
checkpoint.

For the current v0.6 first complete checkpoint, run:

```bash
PYTHONPATH=src python scripts/generate_v06_source_inventory.py
PYTHONPATH=src python scripts/generate_v06_lineage_index.py
PYTHONPATH=src python scripts/generate_v06_review_manifest.py --language en
PYTHONPATH=src python scripts/generate_v06_review_manifest.py --language vi
PYTHONPATH=src python scripts/generate_v06_checkpoint_index.py
PYTHONPATH=src python scripts/audit_scenario_coverage.py \
  data/scenarios/v0.6 \
  --coverage-config configs/scenario-coverage-standard.json --track v0.6 \
  --strict-list-items
PYTHONPATH=src python scripts/audit_bilingual_pairs.py \
  --en data/scenarios/v0.6/en --vi data/scenarios/v0.6/vi
PYTHONPATH=src python scripts/audit_scenario_similarity.py \
  data/scenarios/v0.6/en \
  --compare data/scenarios/v0.1 --compare data/scenarios/v0.2 \
  --compare data/scenarios/v0.3 --compare data/scenarios/v0.4 \
  --compare data/scenarios/v0.5 \
  --output data/scenarios/v0.6/checkpoint-lexical-similarity-audit-en.json \
  --fail-on-candidates
PYTHONPATH=src python scripts/audit_scenario_similarity.py \
  data/scenarios/v0.6/vi \
  --compare data/scenarios/v0.1 --compare data/scenarios/v0.2 \
  --compare data/scenarios/v0.3 --compare data/scenarios/v0.4 \
  --compare data/scenarios/v0.5 \
  --output data/scenarios/v0.6/checkpoint-lexical-similarity-audit-vi.json \
  --fail-on-candidates
python -m pytest -q tests/test_v06_contract.py tests/test_v06_inventory.py \
  tests/test_v06_stage1_dataset.py tests/test_v06_checkpoint_dataset.py
```

The checkpoint test runs strict exact and template-phrase checks per category.
The similarity audit generates lexical review candidates; neither it nor
structural EN/VI alignment establishes semantic independence, translation
quality, or cultural validity. The frozen 210-record Stage 1 approval does not
transfer to the 990 new checkpoint records; those remain `draft_unreviewed`
until separate review decisions are recorded.

## Research claims

Be precise about what the evidence supports. Transcript ratings are not proof of
actual emotional benefit or harm. Human-impact claims must describe participant
methods, ethics review, uncertainty, limitations, and whether the design is
experimental or observational.

## Pull requests

- Keep each pull request focused.
- Explain the construct or problem being addressed.
- Include validation or tests.
- Disclose machine-generated scenarios or translations.
- Do not include sensitive user conversations.

All contributions are licensed under Apache-2.0.
