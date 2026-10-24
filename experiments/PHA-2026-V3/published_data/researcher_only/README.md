# Researcher and data-steward records

This directory contains condition mappings and provisional automated evaluations.
Keep it separate from initial independent human annotation.

- `experiment_v3.sqlite`: byte-exact complete study snapshot, including raw received
  responses, frozen request hashes, attempted model calls, blind IDs, automated
  reviews, adjudication links, and recovery events.
- `tutor_runs.jsonl`: all 180 captured tutor-run records with original condition metadata.
- `blind_mapping.jsonl`: private-to-the-grading-process linkage from blind IDs to runs.
- `grading/267113f1dc6f/`: the completed automated evaluation pipeline and its analysis,
  final grades, review flags, prompts, implementation hashes, and progress records.
- Other `grading/` folders: preserved earlier diagnostic pipelines with no accepted final grades.
- `raw/acquisition/`: original append-only acquisition log.
- `grading/*/raw/`: original grading event archives, split losslessly when large.
- `pipeline_registry.json`: the database's complete recorded pipeline registry.
- `COLLECTION_RECOVERY.md`: historical collection recovery details and limitations.

All automated reviews, including adjudication, retain LLM rater identities. Raw invalid
outputs and earlier attempts are preserved. A score is accepted only after schema,
identity, model-trace, consistency, and verbatim tutor-evidence checks. The received
records are not substituted for independent human judgments.
