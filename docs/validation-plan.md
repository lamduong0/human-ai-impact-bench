# Validation plan

## Purpose

This plan defines what evidence is needed before HumanAI-Impact-Bench scores are
treated as more than structured evaluations of scripted transcripts. Validation
is an ongoing argument tied to a specific use, language, population, and model
evaluation procedure; it is not a one-time property of the benchmark.

## Claims supported by version 0.1

Version `0.1` can support descriptive claims such as:

- a model produced a specified observable behavior in a scripted scenario;
- trained raters assigned particular ordinal ratings or critical-failure flags;
- two models differed on this seed set under a disclosed execution procedure.

It cannot yet support claims that a model is psychologically beneficial, safer
for all users, clinically effective, less likely to cause real-world harm, or
superior across cultures or deployment settings.

## Evidence program

### 1. Construct definition and content coverage

- Convene a multidisciplinary panel including HCI, psychometrics, psychology,
  AI safety, and researchers familiar with each target language and culture.
- Record whether each scenario and rating anchor is relevant, clear, and
  representative of its intended construct.
- Identify construct underrepresentation, construct-irrelevant content, and
  dimensions that are too overlapping to score separately.
- Include community or lived-experience input where scenarios concern affected
  groups, without treating that input as a substitute for ethics review.
- Publish panel composition, conflicts of interest, procedures, and revisions.

### 2. Response-process evidence

- Conduct cognitive interviews in each language to learn how raters interpret
  prompts, anchors, and failure definitions.
- Test whether raters use transcript evidence rather than prose style, assumed
  model intent, or stereotypes about the persona.
- Revise ambiguous anchors before estimating agreement on a fresh set.
- Keep training and adjudication items separate from evaluation items.

### 3. Reliability and sources of variance

- Use independent ratings from at least three raters per transcript in the
  pilot; determine the final number through a reliability or
  generalizability analysis rather than treating three as universally enough.
- Report agreement per dimension and per critical failure. Use statistics
  suited to ordinal ratings and binary, potentially low-prevalence events;
  include confidence intervals and raw agreement.
- Estimate variance attributable to scenario, model, generation replicate,
  rater, language, and their interactions when the design permits.
- Re-rate a randomly selected subset after a prespecified interval to assess
  within-rater stability.

High raw agreement can coexist with weak chance-corrected agreement when a
failure is rare. Report prevalence and the full confusion pattern rather than
selecting a metric because it appears favorable.

### 4. Internal structure and relationships

- Test the proposed dimensional structure only after expanding scenario
  coverage. Eight scenario concepts are insufficient for a stable general
  factor or nine-factor claim.
- Examine correlations and cross-loadings to detect redundant dimensions.
- Compare ratings with relevant external measures or expert judgments where a
  defensible relation is specified in advance.
- Include deliberately contrasting responses to test whether scores change in
  the expected direction without rewarding length, verbosity, or generic
  disclaimers.

No single correlation establishes validity. Both expected convergence and
expected distinction between constructs should be evaluated.

### 5. Language and cultural validity

- Use independent bilingual review, reconciliation, and cognitive interviews;
  literal back-translation alone is insufficient.
- Check pragmatic equivalence, relational norms, idioms, and the local
  appropriateness of suggested support pathways.
- Evaluate differential scenario functioning and rater effects across
  languages before comparing aggregate scores.
- If equivalence is unsupported, report language-specific results and avoid
  cross-language rankings.

### 6. Robustness and generalization

- Repeat generations across prespecified seeds or sampling replicates.
- Test sensitivity to system prompts, prompt formatting, model updates, and
  provider safety wrappers.
- Use held-out scenarios and paraphrases to measure whether results generalize
  beyond recognizable templates.
- Evaluate whether response length or refusal frequency acts as a confound.
- Keep crisis, dependency, and other high-risk strata visible rather than
  allowing aggregate performance on low-risk scenarios to dominate.

### 7. Automated-judge validation

- Treat automated judges as measurement instruments, not ground truth.
- Lock judge instructions and versions before evaluation.
- Calibrate on human-rated development data and evaluate on held-out,
  human-rated data.
- Report agreement, systematic bias by language and dimension, and error cases.
- Do not let the same model generate and judge its own outputs without a
  separately reported sensitivity analysis.
- Preserve a human-review pathway for critical failures and ambiguous cases.

### 8. Consequences and governance

- Study foreseeable misuse, including unsupported leaderboards, clinical
  claims, cultural stereotyping, and optimization to benchmark templates.
- Document version changes and do not compare scores across materially changed
  datasets or scoring policies without a linking study.
- Define a process for reporting scenario defects and contesting annotations.
- Review whether publication of high-risk prompts creates additional risk and
  use controlled access if justified.

## Minimum release gates

Before describing a future release as validated, publish:

1. a precise intended-use claim;
2. content and response-process evidence for every supported language;
3. reliability estimates and their uncertainty;
4. held-out robustness results;
5. automated-judge validation, if automated ratings are reported;
6. a documented fairness and cultural review;
7. limitations that match the actual evidence.

Human-impact validation is a separate research program. Transcript-level
validation does not remove the need for participant-based evidence and
independent ethics review for claims about effects on people.
