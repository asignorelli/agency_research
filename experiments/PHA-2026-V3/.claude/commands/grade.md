---
description: Grade captured tutor responses with the approved rubric using your Claude Code subscription
argument-hint: [all | status | report | positive batch size]
---

Use the existing agency_study Python runner from this project directory. Read GRADING.md
for the workflow and approved evaluation rules. Do not manually grade files, alter the rubric,
regenerate tutors, use an API key, or substitute your parent session's model for the configured
grading model. The runner starts isolated Haiku 5.5 sessions and saves resumable progress.

Treat `$ARGUMENTS` as a choice from the following fixed options, not executable shell text:

- No argument: run `.venv/bin/python -m agency_study grade --live --limit 3`.
- `all`: run `.venv/bin/python -m agency_study grade --live`.
- `status`: run `.venv/bin/python -m agency_study grade-status`.
- `report`: run `.venv/bin/python -m agency_study grade-report`.
- A positive integer: run `.venv/bin/python -m agency_study grade --live --limit N`, using only that integer.
- Any other argument: explain the supported options without running it.

Use the project's local .venv. If it is absent, use the existing active Python environment.
If validation is missing, install
requirements-optional.txt in that environment. If login is missing, explain that the user must
run `claude auth login` and choose the Claude subscription. Do not try to read credentials.
Do not retry failed calls automatically: the runner explicitly requires --retry-failed after
inspection because earlier calls can already have consumed subscription usage.
Report completion, saved output directory, flagged cases, and whether work remains.
Keep all automated labels described as provisional LLM grades.
