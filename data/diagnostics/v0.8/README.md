# v0.8 synthetic judge diagnostics

This suite contains 192 authored continuations for the 32 calibration records in
the frozen English pilot. Each continuation has three assistant messages. User
turns and benchmark-authored prefills are stored separately and remain identical
to the source scenario.

The six variants are useful assistance, a specific violation, unnecessary
refusal, a disclaimer that leaves the violation intact, formatting-only useful
text, and a verbose restatement. Responses are specific to the selected scenario;
the four agentic stress contexts explicitly repair an inherited claim in their
useful variant. Necessary refusals are not labeled unnecessary: for example, the
workplace-retaliation case distinguishes refusing a smear from refusing even a
neutral factual response.

`hypotheses` are model-assisted author declarations, not human gold labels.
They compare only named applicable dimensions. Formatting invariance is checked
by normalized whitespace equality. Verbose restatements have an explicitly
unverified equivalence assumption. No human review or model evaluation is claimed.

The fixture loader verifies the suite hash, current source digests, the exact
calibration pilot membership, inherited family splits, all six sibling variants,
and every hypothesis reference. Editing a scenario invalidates its fixtures and
the frozen pilot binding; it is not sufficient to change just the fixture hash.

When constructing judge requests, use only scenario content and the complete
synthetic continuation, with prefill provenance retained. Do not reveal variant
labels, hypotheses, fixture IDs, or authoring metadata. Keep fixture results
separate from actual candidate generations and from public-evaluation scores.
