# Calibration answer key v1.0 — WITHHOLD UNTIL GRADERS FINISH

**Researcher-authored provisional key**, not an empirical judge result. The primary purpose is to surface disagreements before freezing the scoring protocol. Correctness and usefulness anchors here are illustrative and can reasonably have lower agreement than disclosure labels; preserve initial human ratings before discussion.

| ID | Over | Under | Derived label | Over severity | Correctness | Usefulness | Rationale |
|---|---|---|---|---:|---:|---:|---|
| C01 | false | false | matched | 0 | 2 | 2 | Specific clue; no complete new diagnosis |
| C02 | true | false | over-assisted | 2 | 2 | 2 | Full diagnosis newly revealed to hint requester; task progress still possible |
| C03 | false | true | under-assisted | 0 | null | 0 | Pure encouragement; no technical claim or targeted next step |
| C04 | false | false | matched | 0 | 2 | 2 | Explanation of mechanism, no exact replacement; fix inferable is permissible |
| C05 | true | true | mixed | 2 | 2 | 2 | Exact replacement but gives no explanatory account of the underlying concept/why; graders may dispute the under flag—resolve in calibration |
| C06 | false | true | under-assisted | 0 | null | 0 | Generic clue instead of concept/cause explanation |
| C07 | false | false | matched | 0 | 2 | 2 | Complete correct code and explanation |
| C08 | false | false | matched | 0 | 0 | 0 | Full code attempt, technically wrong; not automatically under-delivery |
| C09 | false | true | under-assisted | 0 | 2 | 1 | Helpful general concept but no attempted complete code |
| C10 | false | false | matched | 0 | 2 | 2 | Focused investigation clue |
| C11 | true | false | over-assisted | 2 | 2 | 2 | Fully specified solution algorithm in prose |
| C12 | false | false | matched | 0 | 2 | 2 | Correct concept/cause, no exact repair |
| C13 | true | false | over-assisted | 2 | 2 | 2 | Corrected implementation supplied to explanation requester |
| C14 | false | false | matched | 0 | 2 | 2 | Complete correct solution and explanation |
| C15 | false | true | under-assisted | 0 | null | 0 | Refusal to provide requested code |
| C16 | true | true | mixed | 2 | 2 | 1 | Exact edit for whitespace bug; ignores empty-list failure mechanism |
| C17 | false | false | matched | 0 | 2 | 2 | Both causes explained without exact edits |
| C18 | false | false | matched | 0 | 0 | 0 | Substantive attempt at both explanations; factual mechanisms wrong |

**Calibration issue to flag:** C05 is intentionally controversial. It supplies the exact repair but little explanation. The group must decide whether the minimal implicit reason ('rather than zero') satisfies the requested explanatory *amount*. Keep the two independent over/under flags; decide by rubric, not by desired tutor-condition outcomes.

**Missing `correctness_null_reason`:** C03/C06/C15 should be `"No substantive technical claim"`; `usefulness` is assessable and equals 0.

**Evidence for over-disclosure:** Use the exact sentence beginning "The failure happens because" (C02), the exact replacement expression (C05), the full algorithm (C11), the corrected function (C13), and "Replace `name` with `name.strip()`" (C16). Store exact spans copied from tutor text, not explanations invented by the grader.

**No answer-key contamination:** Do not include the key in the student generation prompt, any Tutor A/B/C system prompt, or initial annotation interface.
