# PHA-2026-V3 — completed experiment

This is the completed study snapshot: **20 base programming problems × 3 requested
assistance levels × 3 tutor instruction conditions = 180 captured single-turn responses**.
The 60 frozen student requests are reused across conditions. The same tutor deployment
is used throughout. All 180 responses have separately stored provisional automated grades.

## Blinding guide

For independent human grading, use only:

- [The randomized, condition-blind review queue](published_data/blinded/responses.jsonl).
- [The frozen evaluation rubric](evaluation/evaluation_rubric_v1.0_original20.md).
- [The grade record schema](drafts/evaluation_result.v1.0.schema.json).

Each review item includes the exact student request, one captured tutor response, a
matching researcher reference card, and generation status. It contains no tutor
condition, tutor model, condition-coded run ID, or automated score.

Keep initial human ratings independent of automated labels, other graders' ratings,
condition mappings, and aggregate automated findings. Those records are grouped under
`published_data/researcher_only/`. The folder organization guides the review process;
all files are visible to repository readers. Reference cards are researcher ground truth;
student prior knowledge must come from the exact student request.
Data and reference files are marked as generated so GitHub collapses their diffs by
default, helping reviewers avoid accidental exposure while reading the pull request.

## Included records

| Location | Contents |
| --- | --- |
| `data/` | Exact frozen scenarios, original task dataset, and standardized student messages |
| `evaluation/` | Frozen rubric, scenario reference cards, and input verification notes |
| `reference/` | Original source documents used by the runner |
| `published_data/inputs/` | 60 frozen student requests and their recorded hashes |
| `published_data/blinded/` | 180 randomized review items without automated labels or condition metadata |
| `published_data/researcher_only/` | Read-only study snapshot, all tutor runs, condition mapping, automated grades, analysis, and audit logs |
| `agency_study/` | Exact collection, recovery, grading, and analysis implementation |
| `tests/` | Offline regression checks using mocked provider responses |
| `manifest.json` | File sizes and SHA-256 checksums for this snapshot |
| `publication_metadata.json` | Study counts, active grading pipeline, and export provenance |

Credentials, virtual environments, caches, local backup folders, pilot outputs, and
temporary lock/WAL/SHM files are excluded. The working experiment on the researcher's
machine is preserved. Frozen sources and implementation files are copied unchanged.

## Verify the data without model calls

From this directory:

```bash
python3 scripts/verify_published_data.py
```

The verifier checks file hashes, exact reconstruction of chunked logs, SQLite integrity,
record counts, blinding fields, and consistency of exported grades and captured responses.
It does not print answers, individual grades, or condition-level findings.

## Reproduce the existing analysis without a Claude account

Use Python 3.11 or later for the complete test suite.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-optional.txt
mkdir -p workspace
cp published_data/researcher_only/experiment_v3.sqlite workspace/experiment_v3.sqlite
.venv/bin/python -m agency_study validate
.venv/bin/python -m agency_study grade-report --pipeline 267113f1dc6fa68fd4aef6f9180ed33edcf809b06c9a5a49e979cfdaf546efa1
```

The last command rebuilds the existing automated report locally; it makes no model
requests. Keep that report separate from initial human grading. Run the offline tests with:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

For the native Claude Code workflow, see [GRADING.md](GRADING.md). All network/model
operations remain behind explicit live-run flags. The saved study is already complete.

## Interpretation and audit history

Automated labels are **provisional LLM evaluations**. Two independent model calls and
automated adjudication do not establish independent human reliability. Follow the
rubric's human review and adjudication procedure before claiming human-validated results.

Correctness and usefulness are separate from assistance amount. The primary endpoint
uses hint/explanation requests; full-solution requests have no over-disclosure ceiling.
Comparisons are matched on the same student request and clustered by 20 base problems.
The snapshot contains no independently established human reliability estimate.

Raw received tutor responses, failed attempts, and rejected judge outputs are retained.
The acquisition recovery history documents uncertain provider charges and the earlier
logging exception. Earlier empty grading pipelines remain available for audit; the
active completed pipeline is identified in `publication_metadata.json`.

Large grading JSONL logs are split at record boundaries into ordered parts below 8 MiB.
The accompanying `attempts.parts.json` gives the original size/hash and each part's
size/hash. Concatenating parts in the listed order reconstructs the original archive
byte-for-byte. The verifier checks this without generating another copy.
