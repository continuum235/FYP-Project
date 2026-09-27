# Discussion

## Original Question

The comparison output showed PPO missing deadlines, and the question was whether this was a real PPO problem or a bug in the project.

## Initial Finding

At first, the possible explanation was that PPO might be falling back to Greedy if the PPO model file was missing.

However, after checking the project, the PPO model file was present:

```text
simulator/models/ppo_scheduler.zip
```

So the missing-model fallback was not the main reason for the bad PPO result.

## Main Issue

The real problem was a wrong dataset path in the backend comparison API.

The backend comparison service was looking for the carbon dataset here:

```text
backend/simulator/data/snapshots_2026-02-10_IN-2025-5_minute.csv
```

But the actual dataset was here:

```text
simulator/data/snapshots_2026-02-10_IN-2025-5_minute.csv
```

Because the backend path did not exist, the benchmark silently used random fake carbon data. On that fake/random carbon data, PPO appeared to miss deadlines.

## Fix Applied

The comparison service was fixed so that it uses the correct top-level simulator dataset path.

The fix also added a safety check:

```text
If the dataset is missing, raise an error instead of silently using random data.
```

A regression test was also added to confirm that the comparison service points to the correct dataset.

## Verification

After the fix, the tests passed:

```text
PYTHONPATH=backend:. pytest backend/tests/test_comparison_support.py backend/tests/test_ppo_and_benchmark.py -q
9 passed
```

The corrected comparison result showed:

```text
PPO: 39 completed, 0 failed, 0 deadline misses
```

So the earlier result where PPO missed 10 deadlines was caused mainly by the wrong dataset path and random fallback data.

## Why the Output Looks Like This Now

After the fix, the comparison uses the real carbon CSV.

Example output:

| Policy | Completed | Deadline Misses | Carbon Used |
|---|---:|---:|---:|
| Greedy | 37/39 | 0 | 2.96 g |
| Forecast | 36/39 | 2 | 2.87 g |
| Constraint Lexicographic | 39/39 | 0 | 3.28 g |
| PPO | 39/39 | 0 | 3.40 g |

This means:

- Forecast uses the least carbon, but misses deadlines.
- Greedy has zero deadline misses, but does not complete all jobs within the horizon.
- PPO completes all jobs with no deadline misses, but uses slightly more carbon.
- Constraint Lexicographic completes all jobs, has zero deadline misses, and uses less carbon than PPO.

## Best Algorithm Conclusion

For the current project, the best practical algorithm is:

```text
Constraint Lexicographic
```

Reason:

```text
It gives the best balance between job completion, deadline satisfaction, and carbon reduction.
```

It is not always the lowest-carbon policy, but it is the most reliable practical scheduler.

## Presentation Explanation

Use this explanation in the presentation:

> In the current benchmark, Constraint Lexicographic performs best overall because it completes all jobs, has zero deadline misses, and uses less carbon than PPO. Forecast saves slightly more carbon, but it misses deadlines. Therefore, carbon saving alone is not enough; a good scheduler must balance carbon reduction with job completion and deadline satisfaction.

## Research Paper Conclusion

Use this in the research paper:

> Across multiple horizons and random workload seeds, Constraint Lexicographic achieved the most reliable scheduling behavior. It maintained 100% deadline satisfaction and full job completion in the selected benchmark scenarios, while Greedy and Forecast sometimes reduced carbon at the cost of missed deadlines or incomplete jobs. Therefore, the project concludes that constraint-aware scheduling provides the best practical trade-off for carbon-aware ML training workloads.

## Horizon and Seed Meaning

### Horizon

Horizon means how long the simulation runs.

Example:

```text
horizon = 2000
```

In this project:

```text
1 tick = 5 minutes
```

So:

```text
2000 ticks = 2000 * 5 minutes = 10000 minutes = about 166.7 hours = about 6.9 days
```

Simple meaning:

```text
Horizon = simulation duration
```

### Seed

Seed means the random starting point used to generate the workload.

Example:

```text
seed = 42
```

This controls the generated jobs, arrival times, priorities, deadlines, and job sizes.

Using the same seed produces the same workload every time.

Simple meaning:

```text
Seed = workload pattern
```

Different seeds create different scenarios, which helps prove that the result is not based on one lucky workload.

## Suggested Scenarios

Use these horizon and seed values to show that Constraint Lexicographic is better across multiple scenarios.

| Scenario | Horizon | Seed | Constraint Result | Why Useful |
|---|---:|---:|---|---|
| 1 | 500 | 2 | 15/15 completed, 0 misses | Small workload, Greedy/Forecast miss deadlines |
| 2 | 500 | 42 | 9/9 completed, 0 misses | Easy demo case |
| 3 | 1000 | 1 | 25/25 completed, 0 misses | Medium workload |
| 4 | 1000 | 7 | 21/21 completed, 0 misses | Forecast misses more deadlines |
| 5 | 1000 | 57 | 18/18 completed, 0 misses | Shows stability |
| 6 | 1500 | 1 | 38/38 completed, 0 misses | Larger workload |
| 7 | 1500 | 2 | 31/31 completed, 0 misses | Greedy/Forecast miss 4-5 deadlines |
| 8 | 1500 | 7 | 26/26 completed, 0 misses | Good comparison case |
| 9 | 2000 | 1 | 50/50 completed, 0 misses | Strong large scenario |
| 10 | 2000 | 2 | 37/37 completed, 0 misses | Good final benchmark case |

Best scenarios to show in slides:

```text
Horizon 500, Seed 2
Horizon 1000, Seed 1
Horizon 1500, Seed 2
Horizon 2000, Seed 1
```

## Final Project Conclusion

The final conclusion should be:

```text
Constraint Lexicographic is the best practical scheduler in this project because it consistently completes jobs, avoids deadline misses, and still reduces carbon where possible.
```

Important clarification:

```text
Constraint Lexicographic is not always the lowest-carbon policy.
It is the best balanced policy because it protects deadlines and throughput first, then optimizes carbon.
```

PPO can be described as:

```text
PPO is reliable after the dataset-path fix, but in this implementation it does not clearly outperform Constraint Lexicographic. It remains useful as an experimental learning-based scheduler that could improve with more reward tuning and training.
```
I can't see the screenshot — this model has no image input. Paste the headings as text and I'll check them exactly. I verified them from the code instead (frontend/src/App.jsx:318), against a live run at horizon 2000 / seed 42.
Are the headings correct?
Heading	Field shown	Verdict
Policy	policy name	correct
Carbon emitted	total_carbon_g	correct — this is the real carbon story
Total Carbon Saved	carbon_saved_g	misleading, see below
Jobs Completed	jobs_completed/jobs_submitted	correct label, confusing denominator
Deadline misses	deadline_misses	correct
Avg pauses	average_pause_count	correct value, but always 0 → dead column
Score	score[name]	correct, but always "—" → dead column
1. Why Greedy shows 37/39 with 0 deadline misses
No contradiction — the two numbers measure different things.
- 39 is every job the generator planned for the whole 2000-tick window. Jobs arrive gradually, so the last ones show up near tick 1900.
- Greedy finished 37. The other 2 were simply still in progress when the clock ran out:
- job 37 — arrived tick 1883, still WAITING at tick 2000
- job 38 — arrived tick 1967, was 1 of 2 epochs in when time ended
- Their deadlines are ticks 2071 and 2061, i.e. after the horizon. A miss is only recorded when current_tick > deadline_tick (simulator/benchmark.py:216-225), so the run ended first → 0 misses.
- jobs_failed = 0 confirms nothing was actually late.
So "0 deadline misses" means "of the jobs whose deadline arrived during the run, none were late" — not "all 39 finished on time".
This is partly luck of the seed. I ran 7 scenarios:
Horizon	Seed	Greedy
1500	2	27/31, 4 misses
2000	1	45/50, 2 misses
1000	7	19/21, 1 miss
2000	42	37/39, 0 misses
Greedy does miss deadlines on other workloads.
2. Why Score is empty for every policy
The UI never asks for a score. App.jsx:242-250 posts only policies, horizon, seed — no scoring. So ComparisonRunRequest.scoring defaults to None (models.py:116) → ScoreConfig.from_dict(None) returns None → score_results returns None for all policies (scoring.py:39-41) → the table prints — (App.jsx:327).
This is deliberate (there's a test asserting scoring stays off unless explicitly configured), but since the UI never enables it, the column is permanently empty. Verified with weights supplied:
greedy 1.000 | forecast 0.943 | constraint_lexicographic 0.860 | ppo 0.600
Note the score is min-max normalised within the run (scoring.py:29-35), so it always hands out a 1.0 and a 0.0 to the best and worst policy — it ranks, it doesn't measure quality.
3. Why Avg pauses is 0 everywhere
A pause only counts when a job is already running and the policy answers WAIT/PAUSE (benchmark.py:186-189). In this workload that never happens: jobs have 1-2 epochs, so once a job starts it finishes in 1-2 ticks, and the policies run it through. I confirmed total_pause_count = 0 for all four policies in all 7 scenarios above. Not a code bug — the jobs are too small and too short for pausing to ever be worth doing. You'd need multi-epoch jobs or a much lower run threshold to make that column move.
The one genuinely wrong column: "Total Carbon Saved"
carbon_saved_g = baseline of all 39 jobs − carbon of only the completed ones = 1953.14 − ~3 = ~1950 g for every policy. Two separate problems:
- Wrong scale. Simulated use is 0.05 g × intensity/500 per epoch ≈ 0.05 g/job, but baseline_carbon_g is 40-60 g/job. So every policy reports "99.83-99.85% carbon reduction" — the number is noise.
- Inverted ranking. Greedy shows the highest saving (1950.18 g) precisely because it left 2 jobs unrun and never paid their baseline. Skipping work looks like the best carbon saving.
Use Carbon emitted, or carbon_per_completed_job_g which is fair across policies: greedy 0.080, constraint lex 0.084, PPO 0.087.
Want me to (a) wire a scoring toggle so the Score column populates, (b) replace the saved-carbon column with a per-completed-job figure, and (c) drop or relabel Avg pauses?