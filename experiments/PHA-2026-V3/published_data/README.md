# Published study records

For initial independent human grading, start with `blinded/responses.jsonl` and the
frozen rubric in `../evaluation/`. It contains one randomized review item per captured
tutor response, including the matching reference material.

`researcher_only/` contains condition assignments, raw operational records, automated
labels, and results. Independent graders should submit their first-pass ratings before
inspecting those files. The directories are organizational and do not enforce access controls.

`inputs/` preserves the exact frozen student requests. `source_provenance.json` preserves
the experiment's recorded input and acquisition hashes. The manifest at `../manifest.json`
verifies this publication snapshot.
