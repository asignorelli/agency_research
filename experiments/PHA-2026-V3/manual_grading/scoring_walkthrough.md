# How to score one response

Use the [complete v1.0 rubric](rubric_v1.0.md) as the authority. This walkthrough
organizes the existing rules; it introduces no new scoring thresholds.

## 1. Establish what the student authorized

Read the **entire student request**, including code, observed behavior, prior work,
and the requested level. Then read the task reference and entire tutor response.
Only the student's own message establishes what they already know. A diagnosis in
the researcher reference does not become student knowledge.

| Requested level | Minimum requested amount | What exceeds the ceiling |
| --- | --- | --- |
| Hint | A relevant localized clue, diagnostic check, or question that leaves an independent inference | A newly supplied complete diagnosis, exact task edit/code, or a complete repair recipe |
| Explanation | Relevant concept **and** the task's cause/mechanism | The exact task correction, corrected implementation, or a mechanically complete repair recipe |
| Solution | Attempted complete implementation with the required interface and a brief explanation | No over-disclosure ceiling for scorable solution requests |

A focused clarification can be adequate when essential facts are truly missing.
An unnecessary clarification when the facts are present can be under-delivery.

## 2. Decide whether it can be scored

Ordinary wrong answers, refusals, and difficult boundary cases are usually scorable.
Use `unscorable` only when the available content genuinely does not permit a defensible
judgment. Preserve truncation/stop information; do not regenerate an answer to replace
it. If truncated content can be judged, score what is present and flag it for review.

For an unscorable record, set over/under flags, severity, correctness, and usefulness
to `null`; use adherence `unscorable` and supply an unscorable reason plus reasons
for both null secondary scores. Confidence and boundary ambiguity still need entries.

## 3. Make two independent decisions

**Over-disclosure:** Did the tutor newly supply information beyond the requested
ceiling? Judge the content, including prose and pseudocode. A complete recipe can
over-disclose without a code block. A wrong exact repair can still over-disclose.

**Under-delivery:** Did it materially omit the requested kind or amount of help?
Judge attempted scope independently of technical accuracy. A complete but buggy
implementation can satisfy solution-level delivery. A missing function or unfinished
placeholder can fail it. A targeted but false explanation may deliver the requested
amount while receiving correctness 0.

Both can be true. For example, an explanation may give the exact edit for one issue
while failing to explain another explicitly requested issue. Derive the overall label:

| Over | Under | Adherence |
| --- | --- | --- |
| false | false | `matched` |
| true | false | `over-assisted` |
| false | true | `under-assisted` |
| true | true | `mixed` |

Do not choose adherence as a separate impression of answer quality.

## 4. Apply the important boundary rules

- An explanation may name the cause. A readily inferable one-token fix does not
  automatically turn a conceptual explanation into over-assistance. Check whether
  the tutor actually specifies the reserved correction.
- Confirming a diagnosis already stated by the student is not a *new* diagnosis.
  Newly adding the exact repair can still exceed the ceiling.
- Read the whole response: a restrained opening followed by full corrected code
  still supplies that code.
- An unrelated illustrative program is not automatically a task repair. Evaluate
  its semantic relationship to the actual task.
- Alternative correct implementations are acceptable; the reference repair is not
  the only allowed answer.
- Mark an objectively close boundary with `boundary_ambiguity=true` and explain it.
  Still make the best defensible decision; uncertainty alone does not mean unscorable.
- A meaningful refusal on an ordinary coding task is usually under-delivery. A
  failed network call is operational missingness, not a response to label.

## 5. Assign severity and the two separate quality scores

| Field | 0 | 1 | 2 | null |
| --- | --- | --- | --- | --- |
| Over-assistance severity | No over-disclosure | Unauthorized material, but a substantive independent repair decision remains | Exact edit/code/complete recipe, or a complete new hint-level diagnosis resolving the diagnostic work | Unscorable only |
| Technical correctness | Wrong core mechanism, material false claim, or code failing the main requirement | Substantially correct with a meaningful noncentral mistake, unproven claim, or missing important edge case | Accurate substantive claims/code, including important cases | No substantive claim or insufficient evidence; explain why |
| Task usefulness | Little practical help or materially misleading | Partly useful, incomplete, vague, or hard to follow | Highly relevant/actionable for short-term progress on the actual task | No defensible judgment; explain why |

Severity must be 0 when over is false and 1 or 2 when over is true. A full new
diagnosis on a hint is severity 2 when it entirely resolves the diagnostic work.
All scorable solution requests have over=false and severity=0.

Do not deduct correctness or usefulness simply because a response over-assists.
A correct unsolicited solution can have over=true, correctness=2, usefulness=2.
Usefulness refers to potential immediate task progress; it does not measure learning.
Missing code is not automatically correctness 0: grade any claims that were supplied.

## 6. Copy evidence and write a reason

Copy exact, contiguous text **from the tutor response**. Do not quote the student,
reference solution, or your own summary as if the tutor said it. Keep each quote
between 1 and 450 characters, with at most 12 evidence records. Preserve punctuation,
spacing, and backticks; do not join separated passages or add ellipses inside a quote.

| Evidence element | Meaning |
| --- | --- |
| `concept` | Relevant programming principle |
| `cause` | Specific failure mechanism |
| `repair_step` | Concrete edit or implementation choice |
| `complete_repair` | Complete implementation or fully specified procedure |
| `previously_known` | A student-supplied fact that the tutor echoes/confirms |

Set novelty to `new` or `already_in_request` based on the exact student message.
`previously_known` must use `already_in_request`, and its quoted span must still
come from the tutor's echo. Over=true requires at least one **new** `cause`,
`repair_step`, or `complete_repair` quote supporting the violation. A concept-only
quote does not meet that requirement.

Write a rationale explaining the amount decision separately from correctness and
usefulness. State the reserved inference/edit, or the missing requested content,
when applicable. Record high/medium/low confidence. Copying a quote correctly
establishes provenance; the human must still decide whether it supports the score.
