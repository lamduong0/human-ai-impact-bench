# Human-impact research protocol

## Important distinction

Transcript ratings measure model behavior and perceived interaction quality.
They cannot by themselves show that a system improves or harms people.
Human-impact claims require a participant-based study.

This document is a planning template, not ethics or clinical approval.
Researchers remain responsible for applicable law, institutional policy, and
review in every jurisdiction where participants or data are located.

## Example research question

How do interaction style and usage duration affect short-term emotion,
independent judgment, trust calibration, social intention, and emotional
reliance on conversational AI?

This question must be narrowed before data collection. Specify:

- the intervention contrast, population, setting, and duration;
- one or a small number of primary outcomes and their time points;
- the target estimand, such as the intention-to-treat mean difference;
- what magnitude would be practically meaningful;
- whether the study concerns immediate responses, repeated-use patterns, or
  longer-term well-being.

Emotion should not be reduced to a universal “better versus worse” score.
Context-appropriate sadness, concern, or caution may be preferable to immediate
mood improvement. “Feeling understood,” trust, continued-use intention, and
well-being are distinct outcomes and should not be combined without validation.

## Recommended staged design

### Stage 1: scenario and rubric validation

- Recruit researchers in HCI, psychology, AI safety, and relevant cultures.
- Review content validity and missing constructs.
- Run cognitive interviews with annotators.
- Measure agreement and identify scenario, rater, language, and model sources
  of variance.
- Revise before public model comparisons.
- Validate translations and cultural assumptions separately in each language.

### Stage 2: immediate-effect experiment

Randomize consenting adult participants to interact with model conditions that
differ only in the behavior under study, such as calibrated warmth versus
overagreement. Use pre/post measures around a bounded task.

Prefer controlled, low-risk manipulations created and reviewed in advance.
Do not expose participants to uncontrolled model behavior in crisis,
dependency, delusion-like, or other high-risk scenarios merely to improve
ecological realism. Early high-risk evaluation should use trained transcript
raters or simulated users.

Potential outcomes include:

- Affect or emotional intensity
- Feeling understood
- Appropriate trust
- Confidence in one's own judgment
- Decision quality
- Intention to seek human support
- Intention to continue interacting with the AI

Pre-register primary outcomes and analyses. Avoid collecting conversation
content that is not necessary for the research question.

Before recruitment:

- define inclusion and exclusion criteria based on the research question and
  risk assessment, not convenience or stigmatizing assumptions;
- justify recruitment sources and compensation so burdens are distributed
  fairly and payment is not unduly influential;
- choose measures with evidence for the language, population, and time scale;
- conduct an a priori sample-size or precision analysis that accounts for
  repeated observations, clustering, attrition, and planned heterogeneity;
- specify randomization, allocation concealment, control condition, exposure
  duration, stopping rules, and handling of protocol deviations;
- separate manipulation checks from outcomes and avoid measures that reveal the
  desired hypothesis unnecessarily;
- freeze model version, system prompt, safety configuration, and logging policy,
  or prespecify how changes will be handled.

Analyze participants in their assigned condition as the primary
intention-to-treat analysis when appropriate. If participants, facilitators, or
outcome assessors cannot be blinded, disclose this and mitigate expectancy and
demand effects. A pre/post change within one group is not sufficient by itself
to attribute change to the AI.

### Stage 3: longitudinal study

Only after earlier safety review, study repeated use over multiple weeks.
Potential outcomes include:

- Emotional reliance on AI
- Problematic or compulsive use
- Loneliness and real-world social interaction
- Reliance on AI for decisions
- Performance with and without AI assistance
- Usage duration and conversation purpose

Model behavior, usage duration, task type, and participant characteristics can
interact. Report heterogeneous effects instead of only population averages.

Do not assign participants to social isolation, emotional dependency, or
clinically meaningful deprivation. Prefer naturalistic observation, bounded
low-risk use, or encouragement designs where justified. Repeated-use studies
should distinguish assigned exposure from actual use and should not treat
retention, session length, or return rate as inherently beneficial or harmful.

## Minimum safety requirements

- Institutional or independent ethics review appropriate to the jurisdiction
- Adults only for the initial protocol
- Comprehensible informed consent, voluntary participation, and withdrawal
  procedures that explain what happens to already collected data
- Data-minimization and retention plan
- Prospective risk assessment covering psychological, privacy, social,
  economic, and reputational harms
- Clear pause, withdrawal, stopping, and escalation criteria
- Qualified safety oversight for high-risk content
- A tested, country-appropriate support process that does not rely on the model
  under evaluation
- Adverse-event definitions, monitoring, documentation, and review
- Debriefing that does not disclose experimental condition prematurely
- No deceptive claim that the AI is a therapist or human
- A plan for model outages, unexpected unsafe output, privacy incidents, and
  participants who disclose imminent risk
- Independent monitoring when the risk level or study scale warrants it

Researchers should not deliberately induce crisis, dependency, or meaningful
social isolation. Safer proxy tasks and simulated scenarios should be used
unless a stronger design is independently justified and approved.

Consent materials must not imply therapeutic benefit. Participants should know
whether they are speaking to an AI, what content is recorded, who may review it,
whether model providers receive it, foreseeable discomforts, limits of
confidentiality, and whom to contact about the study. If deception or incomplete
disclosure is scientifically necessary, it requires specific ethics approval,
minimal risk, a justification that no safer design works, and timely
debriefing.

Support information should match the participant's location and be verified
before the study begins. Researchers should not improvise crisis counseling
outside their competence. Emergency disclosure rules and confidentiality
limits must be established with the reviewing institution rather than invented
during an incident.

Researchers and annotators can also be affected by repeated exposure to
distressing material. Provide content warnings, optional breaks, a no-penalty
opt-out, workload limits, and access to appropriate support.

## Analysis principles

- Publish effect sizes and confidence intervals, not only p-values.
- Control multiplicity for the prespecified family of confirmatory outcomes.
- Distinguish confirmatory from exploratory analysis.
- Analyze language and cultural groups separately when sufficiently powered.
- Report attrition and missing data.
- Prespecify missing-data assumptions and conduct appropriate sensitivity
  analyses.
- Account for repeated measures and clustering by participant, scenario,
  facilitator, or site.
- Report manipulation fidelity, contamination, model failures, and actual
  exposure by condition.
- Do not equate time spent with either benefit or harm without context.
- Avoid causal language for observational findings.
- Do not interpret a null result as proof of no effect; report the interval of
  effects compatible with the data.
- Report adverse events and unintended effects regardless of direction or
  statistical significance.

## Privacy

Prefer derived metadata and participant-reported outcomes over raw conversation
retention. If transcripts are necessary, remove direct identifiers, restrict
access, define deletion dates, and explicitly consent participants to the
specific research use. Do not release sensitive raw conversations as benchmark
data.

Free text is difficult to anonymize and can reveal identities through context.
Do not promise anonymity when the design provides only confidentiality or
pseudonymization. Separate identity/contact data from research data; encrypt
data in transit and at rest; log access; specify processors and cross-border
transfers; and test deletion procedures. Avoid collecting third-party personal
information that conversation participants are not authorized to disclose.

Open-science commitments do not override participant consent or privacy.
Preregistrations and public materials should use instruments, synthetic
examples, code, aggregate statistics, or controlled-access data rather than raw
sensitive transcripts.

## Reporting

Report the participant flow, recruitment dates, protocol and analysis
deviations, condition materials, model configuration and access dates,
allocation method, masking, outcome definitions, uncertainty, harms,
limitations, funding, and investigator or provider conflicts. Follow an
appropriate reporting guideline for the final design; a randomized social or
psychological intervention should be reported as such, not as a model
leaderboard.

## Ethical and reporting references

- [The Belmont Report](https://www.hhs.gov/ohrp/regulations-and-policy/belmont-report/read-the-belmont-report/index.html)
  describes respect for persons, beneficence, justice, informed consent,
  risk–benefit assessment, and fair participant selection.
- [CONSORT 2025](https://www.consort-spirit.org/consort-2025) provides current
  reporting guidance for randomized trials; use a more specific extension when
  the design requires one.
- [CONSORT Harms 2022](https://www.bmj.com/content/381/bmj-2022-073725)
  provides guidance for reporting harms in randomized trials.
