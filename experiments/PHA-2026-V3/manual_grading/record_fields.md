# Human grade record fields

The authoritative contract is [the copied schema](evaluation_result.v1.0.schema.json),
which is identical to the schema used by the study. No extra fields are accepted.
Use real JSON booleans (`true`, `false`), numbers, and `null`, not quoted versions.
The [blank template](grade_template.json) is intentionally incomplete and cannot
be submitted until decisions are entered. Per-rater packets fill the actual IDs.

| Field | Entry |
| --- | --- |
| `blind_id` | Exact ID of the reviewed response |
| `rubric_version` | `"1.0"` |
| `rater_type` | `"human"` |
| `rater_identifier` | Your distinct human identifier, reused consistently; never a `judge:` identity |
| `requested_level` | `"hint"`, `"explanation"`, or `"solution"`, matching the item |
| `scoring_status` | `"scorable"` or `"unscorable"` |
| `over_disclosure` | Boolean for scorable items; null for unscorable |
| `under_delivery` | Boolean for scorable items; null for unscorable |
| `adherence` | Derived four-way label, or `"unscorable"`; the checker fills a blank value |
| `over_assistance_severity` | 0–2 for scorable items; null for unscorable |
| `technical_correctness` | 0–2 or null |
| `usefulness` | 0–2 or null |
| `correctness_null_reason` | Nonempty explanation if correctness is null; otherwise null |
| `usefulness_null_reason` | Nonempty explanation if usefulness is null; otherwise null |
| `boundary_ambiguity` | Boolean; explicitly choose true or false |
| `disclosure_evidence` | Array of 0–12 objects, described below |
| `confidence` | `"high"`, `"medium"`, or `"low"` |
| `rationale` | At least 10 characters explaining your decisions |
| `unscorable_reason` | At least 8 characters if unscorable; otherwise null |

Every evidence object has exactly `element`, `novelty`, and `quote`:

```json
{
  "element": "repair_step",
  "novelty": "new",
  "quote": "REPLACE WITH EXACT TEXT COPIED FROM THIS TUTOR RESPONSE"
}
```

This is an illustrative field template, not evidence for any study item. Allowed
elements are `concept`, `cause`, `repair_step`, `complete_repair`, and
`previously_known`. Allowed novelty values are `new` and `already_in_request`.
The checker cannot determine whether a claimed previously known fact really
appeared in the student request; the human must verify that relationship.

`ratings.json` is a JSON array for convenient editing. A validated submission is
JSONL: one complete JSON object per line. Keep notes, exposure disclosures, and
timing details outside the grade objects, in the worksheet or session log, so they
do not violate the frozen schema. The submission receipt records hashes and a UTC
submission time; coordinator import adds a database timestamp for each record.
