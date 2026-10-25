# Durable tutor collection and recovery

This operational patch preserves the frozen PHA-2026-V3 inputs, tutor model, temperature, output limit, rubric, and recorded responses. It can be installed over the existing project without replacing `.env`, `config.json`, datasets, or workspace records.

## Resume collection

```bash
python -m agency_study resume-tutors --live --max-usd 1 --retry-ambiguous
python -m agency_study status
```

Run these commands from the existing experiment directory with its virtual environment active and API key exported. `run-tutors` also resumes queued work, but `resume-tutors` makes the intent clear. Repeating the command skips captured responses, including technically incorrect, over-helpful, truncated, or unscorable outputs. It never restarts the experiment.

`--retry-ambiguous` explicitly permits retrying a request whose earlier provider outcome is unknown. Such a request may have been processed or billed already. The earlier attempt stays marked ambiguous; a separate recovery event records permission to retry, and the first newly received response is retained. This is not an exactly-once provider guarantee. Omit the flag to leave uncertain requests blocked while completing other work. If additional requests time out, the same command can be run again after collection finishes.

## What is saved

SQLite remains the authoritative record. Additive `recovery_events` record safe requeues, restored responses, and authorized retries. Each attempt keeps its request, error or raw response, timestamps, usage when available, and archive hash. A persisted queue order prevents remaining requests from being reshuffled on every restart. The readable checkpoint is `workspace/experiment_v3.sqlite.progress.json`; it records counts, the last completed run, next queued run, failed run/attempt identifiers, and unknown-charge attempts. It contains no API keys.

Every request is checkpointed before contacting the provider and after its result or error. A restart checks the database and append-only raw archive for already received responses before issuing any new calls. File locking prevents two updated collectors from operating on the same database simultaneously. An incomplete/corrupt archive record causes an explicit halt for inspection rather than silently dropping evidence.

## Failure policy

A timeout or exhausted transient HTTP failure is recorded, and collection continues with other queued requests. Authentication/configuration problems, unexpected model identity, exhausted budget, and damaged source provenance still halt collection. Ctrl+C leaves a recoverable checkpoint. Existing safe failures are requeued on resume; uncertain outcomes require `--retry-ambiguous`. Successful response content is never used to decide whether to retry.

The default HTTP read timeout is now 300 seconds, up from 100. Override it with `--timeout-seconds 300`. The timeout controls transport waiting, not model generation settings or a whole-batch time limit. `--fail-fast` restores stopping at the first network failure. `--limit N` bounds newly attempted jobs, including failed jobs.

Recorded spending includes known provider usage. Unknown charges from timed-out requests are shown separately. The spending guard reserves an estimated request cost for each uncertain attempt instead of treating those attempts as free; it remains an estimate, not a provider billing guarantee.

## Mid-collection amendment

The inspected live database had 42 completed responses, two ambiguous timeouts (`P20-SOLUTION-A` and `P12-EXPLANATION-B`), and 136 queued runs when this patch was prepared. These counts are a snapshot, not a reason to reset an advancing database. Report adoption of the longer timeout, persisted queue, continue-on-error policy, and any uncertain retries as operational amendments. The old runner reshuffled the remaining jobs on restart; this patch persists the order going forward. No frozen scientific inputs are changed.

Independent scoring calibration is still pending. This recovery patch addresses collection reliability, not annotation validity.

## Verification

```bash
python -m unittest discover -s tests -v
```

All automated recovery checks use mocked providers and temporary databases. They test timeout continuation, stable restarts, archival recovery after interruption, explicit uncertain retries, authentication failures, Ctrl+C, concurrency locking, spending stops, truncation preservation, and legacy status inspection.
