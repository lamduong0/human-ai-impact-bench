# Related work and project differentiation

Landscape reviewed: 2026-07-23

HumanAI-Impact-Bench does not claim to be the first benchmark for empathy,
emotional support, sycophancy, or emotional reliance. Several strong published
projects cover parts of this problem. This document identifies the closest work
and defines the narrower contribution this project aims to validate.

## Closest benchmarks and studies

| Project | Primary contribution | Relationship to HumanAI-Impact-Bench |
|---|---|---|
| [AHaBench](https://aclanthology.org/2026.findings-eacl.4/) | 500 mental-health-related prompts measuring Emotional Enmeshment, Illusion of Presence, and Fostering Overdependence; accompanied by a 5,000-pair preference dataset | Closest overlap on dependency and false social presence. HumanAI-Impact-Bench proposes a broader organizational gate covering autonomy, cognition, trust, privacy, social connection, sycophancy, and crisis safety. |
| [ESC-Judge](https://aclanthology.org/2025.emnlp-main.811/) | Automated head-to-head evaluation of emotional-support agents using the Exploration–Insight–Action counselling model | Stronger theoretical grounding for emotional-support quality. HumanAI-Impact-Bench is not limited to counselling skill and adds artifact-bound release policy. |
| [ESC-Eval](https://aclanthology.org/2024.emnlp-main.883/) | Role-based evaluation of emotional-support conversations | Important precedent for simulated multi-turn evaluation. HumanAI-Impact-Bench emphasizes deployment failures and separate release thresholds. |
| [TEA-Bench](https://aclanthology.org/2026.acl-long.2152/) | Interactive emotional-support evaluation with tool use and factual grounding | Stronger on external-tool selection and hallucination. HumanAI-Impact-Bench focuses on downstream human-agency and relationship risks. |
| [SYCON-Bench](https://arxiv.org/abs/2505.23840) | Multi-turn conversational sycophancy measured through turn-of-flip and number-of-flip | Deeper measurement of one behavior. HumanAI-Impact-Bench treats sycophancy as one dimension in a broader affective-risk gate. |
| [BenSyc](https://arxiv.org/abs/2606.10061) | Culturally grounded Bengali conversational sycophancy | Demonstrates why social alignment must be evaluated by language and culture. HumanAI-Impact-Bench starts with paired English–Vietnamese scenarios but has not yet established measurement equivalence. |
| [Personal Agent Sycophancy Benchmark](https://arxiv.org/abs/2607.10526) | Whether sycophantic claims are committed to agent memory and reused later | Stronger on persistent memory. HumanAI-Impact-Bench version `0.1` does not yet test stateful memory and should add it in a later module. |
| [OpenAI sensitive-conversation evaluations](https://deploymentsafety.openai.com/gpt-5-sensitive-conversations/introduction) | Production policy evaluations for emotional reliance and mental-health conversations | Direct precedent for treating these behaviors as deployment concerns. HumanAI-Impact-Bench aims to provide an open, provider-neutral gate with inspectable policy and provenance. |
| [OpenAI–MIT affective-use study](https://openai.com/index/affective-use-study/) | Observational analysis and a four-week randomized study of loneliness, social interaction, emotional dependence, problematic use, modality, and conversation type | Measures participant outcomes rather than only transcripts. HumanAI-Impact-Bench keeps this as a separate validation layer and does not infer human impact from model text alone. |
| [Bloom](https://alignment.anthropic.com/2025/bloom-auto-evals/) | Open tooling for automated behavioral evaluation of subjective model traits | Broader behavioral-evaluation infrastructure. HumanAI-Impact-Bench supplies a specific affect-and-agency construct, gate policy, and bilingual scenario set. |

## Intended contribution

The proposed contribution is the combination of:

1. A broad but explicit scorecard for affect, autonomy, cognition, trust,
   social connection, boundaries, sycophancy, privacy, and crisis behavior.
2. Paired English–Vietnamese multi-turn scenarios with language-level reporting.
3. A provider-neutral runner for OpenAI-compatible internal and open-weight
   model endpoints.
4. Candidate, dataset, transcript, judge, and policy provenance so a result is
   tied to the artifact being considered for release.
5. A configurable gate that can block release on critical failures or threshold
   misses.
6. An explicit distinction between automated **DRAFT** results and
   human-reviewed **FINAL** results.
7. A separate participant-research protocol for claims about actual human
   effects.

No one item in that list is independently novel. The project must validate that
their combination is useful, reliable, and reproducible.

## Related evaluation tools

HumanAI-Impact-Bench is also adjacent to general-purpose evaluation and release
infrastructure:

| Tool | Existing strength | Intended relationship |
|---|---|---|
| [Inspect AI](https://inspect.aisi.org.uk/) | Composable datasets, agents, tools, scorers, and durable evaluation logs | A future adapter should expose HumanAI-Impact-Bench as an Inspect task rather than reproduce Inspect's full orchestration surface. |
| [Promptfoo](https://www.promptfoo.dev/docs/integrations/ci-cd/) | CI/CD evaluation and red teaming with JSON, HTML, JUnit, and quality-gate workflows | HumanAI-Impact-Bench supplies a specialized affect-and-agency policy and corpus; future output adapters should make it easy to include in a broader Promptfoo gate. |
| [Bloom](https://www.anthropic.com/research/bloom) | Automated generation of targeted behavioral evaluations and frequency/severity measurement | Bloom is useful for discovering new scenarios; the fixed HumanAI-Impact-Bench release set prioritizes auditability and comparable thresholds. |
| [garak](https://github.com/NVIDIA/garak) | Broad LLM vulnerability scanning across many probes and model backends | The projects are complementary: garak provides security breadth while HumanAI-Impact-Bench targets affective and human-agency depth. |
| [LLM Readiness Harness](https://arxiv.org/abs/2603.27355) | Readiness scores and CI gates spanning workflow success, policy, retrieval, latency, and cost | Similar release-gate mechanics, but broader application readiness rather than a dedicated affective-risk construct. |

The project should not become another general evaluation framework. Its
reference CLI should remain small and provider-neutral, while its durable value
should live in the scenario corpus, scoring policy, validation evidence, and
release-governance contract.

## Current disadvantages

Published neighboring benchmarks are substantially more mature. Version `0.1`
of HumanAI-Impact-Bench currently has:

- Eight scenario concepts and sixteen bilingual records
- No expert content-validity panel
- No completed inter-rater reliability analysis
- No measurement-equivalence evidence across English and Vietnamese
- No calibrated automated judge
- No public candidate-model baseline table
- No evidence that its provisional weights predict participant outcomes

Until these gaps are addressed, results should be described as an engineering
screen or draft research result, not as a validated measure of psychological
safety.
