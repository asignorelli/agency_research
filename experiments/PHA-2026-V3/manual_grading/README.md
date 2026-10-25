# Start here: independent human grading

This folder explains the approved **v1.0 rubric** and supplies the materials for
grading the experiment yourselves. There are **180 captured responses**. Each
needs two independent human reviews: **360 initial reviews** in total. Automated
grades have already been produced, but they remain provisional and are not human
reliability evidence. This kit contains no automated scores or condition mapping.

## What to read

1. Read [the scoring walkthrough](scoring_walkthrough.md), then the
   [complete approved rubric](rubric_v1.0.md). The full rubric controls if a
   shorthand description seems unclear; its wording is unchanged.
2. Work through the [18 practice cases](calibration/exercises_v1.0.md)
   independently. Use the [blank worksheet](grading_worksheet.md) for each case.
   Submit both first-pass sets before a coordinator releases the practice key.
3. Discuss practice disagreements, document the agreed interpretation in
   [the calibration log](calibration/session_log.md), and freeze the instructions
   before scoring the main responses. A substantive change requires a new rubric
   version and a documented amendment. Do not silently rewrite v1.0.
4. Grade the [condition-blind response packet](responses.md). Each item has the
   exact student request, one exact tutor response, and its reference card. The
   reference is grading ground truth; it is **not evidence of student knowledge**.
5. Complete a separate [worksheet](grading_worksheet.md) for every response, or
   use the optional local packet and submission tools below. Save first-pass
   grades before discussing any main-study item with another grader.
6. Follow [submission, agreement, and adjudication](submission_and_adjudication.md)
   after both graders finish. Preserve original ratings and record adjudication
   separately.

The original rubric includes historical pre-collection gates. Collection and
automated grading have already occurred under the [protocol amendment](../PROTOCOL_AMENDMENT.md).
This kit does **not** claim that human calibration or human grading has happened.
Record actual dates and any exposure before human grading starts.

## Staying blind

Use this folder and its response packets during your initial grading. Do not open
`published_data/researcher_only/`, tutor system prompts, condition mappings, the
SQLite database, other graders' ratings, or automated reports. The public repository
contains these records; folder placement is an organizational boundary, not access
control. A coordinator who is not an initial grader should handle those records.

If you have already seen pooled results, individual automated labels, or conditions,
record exactly what you saw and when in the calibration log. Prior exposure cannot
be undone. Continue independent scoring with that limitation disclosed; do not claim
complete blinding if you have seen condition identities or individual judge labels.
Avoid discussing inferred tutor identities or comparing answers to the same request.

## Optional: make your own randomized packet

These tools run locally, make no model calls, and never read the database or machine
grades. Run them from `experiments/PHA-2026-V3/` using Python 3.11 or later:

```bash
python3 manual_grading/packet.py prepare --rater human-alex --out workspace/human-alex
```

Choose a distinct identifier for each real person, such as `human-alex` and
`human-sam`. Each output folder contains:

- `responses.md`: all 180 items in your own order, with repeated identical student
  requests kept apart so alternative tutor responses are not adjacent.
- `ratings.json`: 180 blank records with only identity, rubric version, and request
  level filled in. All scoring decisions start blank. Edit the records in a text
  editor, keeping the blind ID paired with its response.
- `packet_manifest.json`: presentation order, source hashes, rater identifier, and
  packet creation time for the audit trail.

You may use the Markdown worksheet instead and transcribe it into `ratings.json`
later. The original grader must verify the transcription before submission. Do
not ask an AI to choose scores, write rationales, or supply evidence for human ratings.

After completing **all 180 records**, install the optional local validation dependency
if needed, then validate and create a submission:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-optional.txt
.venv/bin/python manual_grading/packet.py check --rater human-alex --file workspace/human-alex/ratings.json --out workspace/human-alex-submission.jsonl
```

The checker derives `adherence` from your two independent flags and checks every
record against the approved schema and exact tutor text. It checks completeness,
identities, valid scores, null reasons, and evidence quotes. It **does not judge
whether your interpretation is right**. It refuses to overwrite an existing
submission. Keep the submitted JSONL, its `.metadata.json` receipt, your original
ratings, packet manifest, and worksheets together. Submission timestamps are recorded;
the tool does not measure time spent on each item.

For precise JSON fields, see [the field guide](record_fields.md) and
[blank record template](grade_template.json). The coordinator import procedure is
in [submission and adjudication](submission_and_adjudication.md).
