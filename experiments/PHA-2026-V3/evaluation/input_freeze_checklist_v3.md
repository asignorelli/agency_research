# Input freeze checklist — PHA-2026-V3

The active study imports the 20 original LeetCode tasks and standardized V2 messages. Independent grader calibration remains pending under the automated-first evaluation protocol.

- [x] Restore original problems 3, 4, 9, 11, and 20 in the runnable dataset.
- [x] Match all attempt-code blocks and task titles to the original dataset.
- [x] Remove Scenario 9's unverified timeout claim and align its observed example.
- [x] Correct Scenario 20's metadata to describe returning infinity for an unreachable amount.
- [x] Align all 20 researcher cards with the dataset, code, observations, and exact message hashes.
- [x] Preserve source upload and previous study records; use a separate V3 configuration and database.
- [x] Import 20 message candidates with explicit standardized-input origin and zero provider calls.
- [x] Verify the 60-request/180-run crossing in a temporary offline test database.
- [ ] Researcher personally reviews the 20 active openings and cards.
- [ ] Researcher runs `python -m agency_study freeze-students --ack-reviewed` to attest to input review and freeze the main study's request manifest.
- [ ] Review the held-out tutor pilot and projected cost before main provider collection.
- [ ] Before interpreting evaluation results, disclose grader identity, calibration status, missingness, and any later rubric or card revisions.

Technical input checks do not establish independent human annotation reliability or effects on student learning.
