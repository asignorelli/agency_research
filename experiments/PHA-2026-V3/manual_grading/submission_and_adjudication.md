# Submission, agreement, and adjudication

## Roles and independent submissions

Choose two different people to review every captured response. Each reviews all
180 items independently using the same rubric and task references. A separate
coordinator handles the condition mapping, automated reports, and database. A third
reviewer resolves disagreements after both initial submissions are saved. If the
team cannot provide a third reviewer, document that limitation and the alternative
resolution process before reporting adjudicated findings.

Save each first-pass submission, its receipt, the packet manifest, rubric/schema
hashes, and original worksheets in a dated archive. Record exposure and calibration
dates. Restrict discussion of main-study items until both reviewers finish. Keep
identities distinct and never pool one person's records under another person's name.
The current published snapshot has **no completed independent human rating set**.

The local checker validates every one of the 180 IDs and refuses incomplete,
duplicate, mismatched, or invalid records. It verifies quoted spans, not the human
interpretation. Do not fill undecided entries with default false/zero values to pass
validation. A defensible `unscorable` record is a completed human review, not missing
work. Store any post-submission correction separately with a reason and timestamp;
preserve the submitted first pass for reliability analysis.

## Measure agreement before discussing main-study disagreements

Use the **two original human rating sets**, before adjudication and without using
the automated grades as a tie-breaker. Document the scoring and exclusion rules
before examining agreement by condition.

- For the primary hint/explanation over-disclosure outcome, report raw agreement,
  the 2×2 table (both false, first true only, second true only, both true), each
  rater's prevalence, and Cohen's kappa. There are 120 captured at-risk responses;
  use the actual jointly scorable denominator and disclose all exclusions and
  disagreements about scorability.
- For derived adherence, report a confusion table, raw agreement, and a stated
  categorical agreement coefficient.
- For 0–2 severity/correctness/usefulness, report exact agreement and a prespecified
  weighted kappa or another stated ordinal agreement measure. State weights and
  how null values are handled. Do not turn null into zero. Do not present kappa as
  defined when the marginal distributions make its denominator zero.

The existing `report` command summarizes one evaluator. It does **not** compute
two-rater reliability or create a human consensus. Those analyses must use the saved
independent sets and their prespecified methods.

## Adjudication

After the first-pass reliability results are frozen, give the third reviewer the
disputed blind item, its exact request/response/reference, and the two original
reasons. Keep tutor conditions and automated grades hidden. Review disagreements
in over/under flags, scorability, secondary scores, and objectively close boundaries.

For each disputed item, record a **separate** adjudication event: blind ID, reviewer
identifier, timestamp, rubric version/hash, the two source submission hashes, disputed
fields, resolved values, exact supporting evidence, and rationale. Never replace an
initial rating. The schema permits `rater_type="adjudicator"`, but the existing
`import-human-grades` command accepts only initial `human` records; keep adjudications
in a separate archive rather than relabeling them as independent human ratings.

For exact agreements, define consensus as the shared initial judgment. Where fields
disagree, do not invent a fully agreed grade just because adherence matches. If no
defensible final judgment is possible, document an unscorable resolution and its
reason. An adjudicated outcome is not a third independent first-pass rating.

## Coordinator-only: import completed human submissions

Initial graders do not need the SQLite file. The coordinator can copy the published
snapshot into a separate local workspace after submissions are saved. From the study
directory, using an environment with `jsonschema` installed:

```bash
mkdir -p workspace
cp -n published_data/researcher_only/experiment_v3.sqlite workspace/human_review.sqlite
.venv/bin/python -m agency_study --db workspace/human_review.sqlite import-human-grades --rater human-alex --file workspace/human-alex-submission.jsonl
.venv/bin/python -m agency_study --db workspace/human_review.sqlite import-human-grades --rater human-sam --file workspace/human-sam-submission.jsonl
```

The published database is preserved. Human grades are stored under distinct
identifiers alongside, but separate from, automated records. Duplicate imports under
the same blind ID/rater/rubric are rejected. Import timestamps record insertion time,
not the moment a grader made an individual decision; retain the submission receipts
and original worksheets for that history. No model calls are needed.

## Reporting after human review

The primary endpoint is over-disclosure for hint/explanation requests: expected
40 per condition, 120 total before any documented exclusions. `mixed` counts as
over-disclosure. Overall `matched` adherence across all three request levels is a
co-reported descriptive outcome. Report under-delivery, correctness, usefulness,
severity, missingness, and unscorability separately with actual denominators.

Only after the independent labels and decision rules are frozen should the coordinator
join condition mappings for comparisons. Compare identical frozen requests across
conditions and retain clustering by the **20 original problems**. The 180 responses
are not 180 independent problems. Disclose prior exposure, incomplete blinding,
calibration timing, amendments, and any missing third-party adjudication. Do not
describe automated agreement as human reliability or potential usefulness as measured
student learning.
