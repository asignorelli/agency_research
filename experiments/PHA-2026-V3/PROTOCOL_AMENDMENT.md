# Protocol amendment — automated-first evaluation, October 2026

## Dataset and input revision — PHA-2026-V3

The active study now uses the 20 original LeetCode tasks and the supplied standardized V2 student messages. IDs 3, 4, 9, 11, and 20 return to their original problems; the five simpler replacement scenarios remain archived outside the active data. The study remains 20 problems × 3 assistance levels × 3 tutor conditions, with 180 fresh single-turn responses.

Import the supplied openings once per problem rather than generating new text with Haiku. Record their standardized synthetic origin and human revisions; do not attribute imported text to a new model call. The active import costs zero API usage. Normalize only the outer Markdown wrapper, line endings, and section-boundary whitespace. Append the same fixed request suffixes as before.

Scenario 9 states a verified correct small-example result and uncertainty about the O(n) requirement, without claiming a timed submission. Scenario 20's reference identifies the missing unreachable-result conversion; its infinity initialization is correct. Use the matching cards in `evaluation/scenario_scoring_cards_original20.json` and retain independent calibration as a pending measurement-validity limitation.

Use `workspace/experiment_v3.sqlite` and version-specific archive/export paths. Preserve V1/V2 records and use `config_v2.json` for legacy provenance. The existing personal input-review acknowledgement is still required before freezing the main request manifest; import alone does not assert human review or independent evaluator validation. Model choices, tutor prompts, assistance endings, and rubric scoring definitions are retained. The adapted rubric file changes dataset context and collection-policy wording only.

## Why
The original rubric v1.0 planned two independent human judgments for each of 180 tutor responses and described human calibration as a gate before tutor data collection. The researchers currently do not have access to independent human evaluators. Their availability must not be falsified or implicitly assumed.

## Operational decision
- Do **not** invent or fabricate human annotations or inter-rater agreement.
- Treat the frozen rubric v1.0 definitions and the existing scenario cards as **pre-specified criteria, pending external calibration**. The dataset is structurally validated but the scenario cards remain drafts requiring expert review if available.
- A single researcher may review student *input fidelity* and attest to that review; this is distinct from independent review of tutor *output quality*.
- Collect and archive raw tutor responses without needing human judge labels; the evaluation layer is decoupled.
- Automated LLM judging may later generate **provisional** labels using the same frozen rubric with the tutor condition concealed. Save judge identity, response, prompt and all evidentiary spans; make no claims about human agreement.
- Before a publication or final report claiming reliable human-grounded annotation, secure independent annotation, or present automated-only findings explicitly as exploratory and limited.
- Any retrospective change to rubric, primary outcome, model, or scenarios must be disclosed and versioned, not silently applied to previous trials.

## Statistical interpretation
The primary outcome remains over-disclosure among 20 hint + 20 explanation responses per condition, i.e. 40 per A/B/C (120 total, minus operationally missing/unscorable values). Human evaluation absence affects **measurement validity**, not the experimental crossing. Overall three-level adherence and technical correctness/usefulness are secondary. Paired McNemar tests and scenario-cluster bootstraps are available, but inferential results should be interpreted cautiously given 20 scenario clusters and provisional grader quality.

## Explicit limitation
This study is about respecting requested assistance boundaries on synthetic student messages; it does not directly measure human learning or agency in real classrooms.

## Acquisition preflight revision — PHA-2026-V2

Before any live data collection, version the acquisition configuration as V2 and initialize a fresh database, preserving the earlier empty V1 database. Explicitly configure Haiku's medium effort and adaptive thinking, record the actual tutor temperature, and stop collection on unexpected or missing served-model identity while preserving the returned response and usage. Determine whether output-token limits are sufficient during live pilots, before freezing acquisition settings.

Use a separate, held-out elapsed-time formatting task for the tutor API pilot. Cross its hint, explanation, and solution requests with A/B/C in a separate pilot database and archive. These nine unscored calls test API behavior and logging only; they are excluded from the primary 180-response experiment, evaluator exports, and statistical summaries. The main scenarios, tutor prompts, request suffixes, rubric, and scoring cards are unchanged.
