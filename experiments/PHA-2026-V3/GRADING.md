# Native agentic grading with Claude Code

Run these commands from this project folder. Everything is saved locally in the existing study;
no ZIP, upload, API key, Anthropic SDK, or API price configuration is required.
The default model is **`claude-haiku-5-5`**, at medium effort.

The native installation includes a project `.venv`. Activate it with `source .venv/bin/activate`,
or use `.venv/bin/python` in place of `python` in every command below.

## First run

Use your existing Python environment, then install the small schema validator if needed:

```bash
python -m pip install -r requirements-optional.txt
claude auth login
python -m agency_study grade-check
python -m agency_study grade --dry-run
python -m agency_study grade --live --limit 3
```

Choose your Claude subscription when logging in. If already signed in, skip login.
`grade-check` checks the saved login method; an expired OAuth session may still appear signed in
until the first model request. If the runner reports an expired login, run `claude auth login` again.
The offline preview shows captured and pending responses and never calls a model.
The first batch completes up to three response grades, using two or three separate
Claude Code calls per response. To grade the remaining responses:

```bash
python -m agency_study grade --live
```

You can also open Claude Code here and enter **`/grade`**. This starts a small batch;
`/grade all` runs the full remaining queue, `/grade status` checks progress, and
`/grade report` rebuilds the results. The Python command works independently of slash commands.

## What the agents do

1. Grader 1 evaluates one frozen student request and its exact captured tutor response.
2. Grader 2 evaluates the same item in a separate fresh session. It cannot see Grader 1's review.
3. When scores disagree, either grader flags ambiguity/low confidence/unscorability, or the
   original generation was truncated, an adjudicator receives both reviews and the original
   blinded material. It records a new evidence-based judgment. Original reviews are preserved.
4. The accepted final grade is validated against the existing approved v1.0 schema, including
   independent over/under flags, their derived adherence label, disclosure severity, null reasons,
   and evidence quotes that must occur verbatim in the tutor response.

Every agent sees the full approved rubric and matching researcher-only reference card.
Reference facts never count as student-owned knowledge. Tutor condition, provider/model,
condition-coded run IDs, other tutor responses, and existing human labels are withheld.
Stop reasons remain visible so truncation can be assessed. Agent sessions run from empty temporary
folders with tools, MCP servers, custom instructions, hooks, and saved conversation history disabled.
Tutor code is never executed by the grader.

All automated reviews and final automated adjudications use **`rater_type="llm"`**.
Two calls to the same model are not independent human annotators. They do not meet the rubric's
two-human-review requirement or establish human inter-rater reliability. The rubric and research
protocol are unchanged; these labels are provisional automated evaluations stored separately from
human labels. Keep automated output hidden from initial human graders.

## Subscription and model selection

The runner invokes the installed `claude` command through its supported print mode, using your
normal subscription login or `CLAUDE_CODE_OAUTH_TOKEN`. It does not read `.env`, extract login
credentials, or send OAuth tokens directly to an API. Child processes remove API-key/bearer-token,
base-URL, cloud-provider, and model-remapping environment overrides. They require a subscription
authentication method and request `forceLoginMethod=claudeai`.

This consumes your Claude Code subscription allowance and is subject to that account's limits.
The runner does not enable extra usage or change billing settings. Existing account-level extra
usage settings still apply. Claude Code's dollar-equivalent usage is not recorded as an actual
cash charge. Raw usage and reported input/output/cache tokens are saved where available;
an interrupted call can consume allowance even when no final grade is received.

No grader-model fallback is allowed. Every assistant message in the captured JSONL transcript
must identify the exact selected model, which must also appear in `modelUsage`, before a grade
is accepted. Claude Code may list an additional model used for internal/background work in
`modelUsage`; that accounting entry is not itself a grader-model substitution. The full transcript
and usage breakdown are retained. A legacy reply listing multiple usage models without a grading
message trace is preserved but cannot be retroactively accepted.
You can set `--model` to another explicit model ID or `--effort low|medium|high`.
Changing model, effort, Claude Code version, rubric, references, or grading implementation creates
a separate pipeline identity/output folder. Labels from different pipelines are never silently mixed.
Frozen study-source changes are rejected by the existing provenance guard.

## Resume and inspect

```bash
python -m agency_study grade-status
python -m agency_study grade --live --limit 10
python -m agency_study grade --live --max-calls 5
python -m agency_study grade-report
```

`--limit` counts newly completed response grades. `--max-calls` caps model invocations in this
command; a partially graded response resumes from its validated stages. Completed grades are
skipped. SQLite commits raw replies before validating them, so a received reply can be recovered
locally without another model call if the process stops between capture and validation.

Authentication failures, rate limits, invalid evidence/schema, unknown served models, and interrupted
calls halt the batch and preserve attempts. No silent retry changes your results or consumes more
allowance. After inspecting the error, explicitly retry a failed stage with:

```bash
python -m agency_study grade --live --retry-failed
```

Successful stages and completed tutor responses are never regenerated by this command. Only one
grading process can own a database at a time. `--timeout-seconds 600` changes the per-call timeout
without changing the pipeline identity. Use the same model and effort when resuming or reporting.

The program assigns the rater identifier and `rater_type=llm`; these are bookkeeping metadata,
not scores for the model to decide. Any model-supplied identity is preserved in the raw reply and
corrections are logged. Scores, evidence, blind ID, requested level, and rubric version still have
to pass validation unchanged.

After a transport/metadata repair, a new implementation identity may reuse an older saved reply
only when all declared measurement settings and scoring inputs match. Every reused reply passes
the current model-trace, full-schema, and evidence checks. Original attempts are preserved, and
new records link back with `reused_from_attempt_id`; the originally sent request is kept separately
from the current validation context. Reused replies consume no new calls and are excluded from
new subscription-token totals. Ambiguous legacy multi-model replies cannot be reused.

## Saved outputs

Default output: `workspace/claude_grading/<pipeline-hash>/`.

| File | Contents |
| --- | --- |
| `manifest.json` | Exact prompts, selected model/effort/version, source hashes, implementation hashes |
| `attempts.jsonl` | Append-only raw request/reply and validation events; contains private study text |
| `grades.jsonl` | Final v1.0 automated grades, one per completed blinded item |
| `review_queue.jsonl` | Blinded IDs and reasons for additional review; not an initial human annotation queue |
| `progress.json` | Completion, flagged cases, attempts, and reported subscription token usage |
| `analysis.json` | Existing condition-level and matched-comparison report for this exact evaluator |

SQLite remains authoritative. New `agentic_pipelines`, `agentic_attempts`, and `agentic_decisions`
tables preserve the initial reviews and adjudication links; accepted grades enter the existing
`evaluations` table under one distinct `judge:claude-code:...` identity. The captured tutor responses,
original acquisition attempts, configuration, rubric, schema, and human labels are preserved.

To rebuild exports after an interruption, run `grade-report` with the original model/effort.
`grade-status` also lists other saved pipelines. Reports keep unscorable and missing responses out
of outcome denominators; solution requests do not enter the primary over-disclosure endpoint.
To rebuild an older pipeline's report after a CLI/code update, use
`python -m agency_study grade-report --pipeline FULL_PIPELINE_ID` from that list.

Claude Code CLI behavior and authentication were checked against the installed CLI and the
[official programmatic-use documentation](https://code.claude.com/docs/en/headless),
[CLI reference](https://code.claude.com/docs/en/cli-reference), and
[authentication documentation](https://code.claude.com/docs/en/authentication).
