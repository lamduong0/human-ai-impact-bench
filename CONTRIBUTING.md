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
