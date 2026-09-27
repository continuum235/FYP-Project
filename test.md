# Test Report

Generated after the carbon-dataset path fix described in `discussion.md`.

## 1. Summary

| Metric | Count |
|---|---:|
| Total tests collected | 56 |
| **Passing** | **56** |
| **Failing** | **0** |
| Errors (collection/import) | 0 |
| Skipped | 0 |
| Xfailed / Xpassed | 0 |
| Warnings (not failures) | 116 |

**There are currently 0 failing tests.** See section 5 for why nothing fails, and
section 6 for the tests that *did* fail before the fix.

Last full run:

```text
platform linux -- Python 3.14.7, pytest-9.0.2, pluggy-1.6.0
rootdir: green-ai-scheduler/backend
configfile: pytest.ini
collected 56 items

56 passed, 116 warnings in 184.25s (0:03:04)
```

## 2. How to run

```bash
# whole suite
cd green-ai-scheduler/backend && python -m pytest -v

# only the carbon-dataset / comparison tests referenced in discussion.md
cd green-ai-scheduler
PYTHONPATH=backend:. python -m pytest \
  backend/tests/test_comparison_support.py \
  backend/tests/test_ppo_and_benchmark.py -q
```

## 3. Per file

| File | Test functions | Collected items (with params) | Passing | Failing |
|---|---:|---:|---:|---:|
| `backend/tests/test_comparison_support.py` | 10 | 10 | 10 | 0 |
| `backend/tests/test_execution_engine.py` | 3 | 3 | 3 | 0 |
| `backend/tests/test_gaiq_engine.py` | 3 | 3 | 3 | 0 |
| `backend/tests/test_greedy_policy.py` | 11 | 11 | 11 | 0 |
| `backend/tests/test_orchestrator.py` | 12 | 29 | 29 | 0 |
| `backend/tests/test_persistent_store.py` | 3 | 3 | 3 | 0 |
| `backend/tests/test_ppo_and_benchmark.py` | 5 | 5 | 5 | 0 |
| **Total** | **47** | **56** | **56** | **0** |

`test_orchestrator.py` has 29 collected items from 12 functions because 9 functions are
parametrised over the `[greedy]` / `[ppo]` policy fixtures. `conftest.py` and
`test_api.py` contribute no test cases (`test_api.py` only defines a `client` fixture).

## 4. Every test, by name

Status column is from the run above; **all 56 are PASSED**.

### `test_comparison_support.py` (10)

| # | Test name | Status |
|---:|---|---|
| 1 | `test_workload_generation_is_reproducible` | PASSED |
| 2 | `test_scoring_normalizes_each_comparison_set` | PASSED |
| 3 | `test_scoring_is_disabled_without_explicit_configuration` | PASSED |
| 4 | `test_comparison_service_uses_top_level_simulator_dataset` | PASSED **(new)** |
| 5 | `test_comparison_service_does_not_look_for_dataset_under_backend` | PASSED **(new)** |
| 6 | `test_carbon_loader_reads_real_dataset_instead_of_random_fallback` | PASSED **(new)** |
| 7 | `test_carbon_loader_raises_instead_of_returning_random_data` | PASSED **(new)** |
| 8 | `test_carbon_loader_raises_on_dataset_without_carbon_column` | PASSED **(new)** |
| 9 | `test_comparison_service_run_reports_missing_dataset` | PASSED **(new)** |
| 10 | `test_comparison_service_run_records_real_dataset_path` | PASSED **(new)** |

### `test_execution_engine.py` (3)

| # | Test name | Status |
|---:|---|---|
| 11 | `test_execution_reports_session` | PASSED |
| 12 | `test_cooperative_pause_mid_epoch` | PASSED |
| 13 | `test_event_loop_not_blocked` | PASSED |

### `test_gaiq_engine.py` (3)

| # | Test name | Status |
|---:|---|---|
| 14 | `test_baseline_computed_from_profile` | PASSED |
| 15 | `test_update_profile_rolling_average` | PASSED |
| 16 | `test_grade_thresholds` | PASSED |

### `test_greedy_policy.py` (11)

| # | Test name | Status |
|---:|---|---|
| 17 | `test_run_when_clean_grid` | PASSED |
| 18 | `test_wait_when_dirty_grid` | PASSED |
| 19 | `test_pause_when_running_and_dirty` | PASSED |
| 20 | `test_hold_band_running_keeps_job` | PASSED |
| 21 | `test_high_carbon_waits_despite_performance_target` | PASSED |
| 22 | `test_deadline_pressure_forces_run` | PASSED |
| 23 | `test_hysteresis_running_stays_on_clean` | PASSED |
| 24 | `test_force_run_only_on_deadline_and_max_pause` | PASSED |
| 25 | `test_forecast_policy_waits_when_carbon_is_high_but_falling` | PASSED |
| 26 | `test_forecast_policy_runs_when_forecast_stays_clean` | PASSED |
| 27 | `test_constraint_lexicographic_policy_prioritizes_deadline_then_target_then_carbon` | PASSED |

### `test_orchestrator.py` (29 items from 12 functions)

| # | Test name | Status |
|---:|---|---|
| 28 | `test_job_lifecycle[greedy]` | PASSED |
| 29 | `test_job_lifecycle[ppo]` | PASSED |
| 30 | `test_pause_resume_accumulates_carbon[greedy]` | PASSED |
| 31 | `test_pause_resume_accumulates_carbon[ppo]` | PASSED |
| 32 | `test_manual_pause_not_overridden[greedy]` | PASSED |
| 33 | `test_manual_pause_not_overridden[ppo]` | PASSED |
| 34 | `test_system_pause_on_high_carbon[greedy]` | PASSED |
| 35 | `test_system_pause_on_high_carbon[ppo]` | PASSED |
| 36 | `test_startup_reconciliation` | PASSED |
| 37 | `test_single_flight_two_jobs[greedy]` | PASSED |
| 38 | `test_single_flight_two_jobs[ppo]` | PASSED |
| 39 | `test_decide_called_once_per_tick[greedy]` | PASSED |
| 40 | `test_decide_called_once_per_tick[ppo]` | PASSED |
| 41 | `test_profile_update_uses_energy_not_carbon` | PASSED |
| 42 | `test_profile_persists_across_store_instances` | PASSED |
| 43 | `test_baseline_set_once_at_submission[greedy]` | PASSED |
| 44 | `test_baseline_set_once_at_submission[ppo]` | PASSED |
| 45 | `test_deadline_pressure_forces_run_on_tick[greedy]` | PASSED |
| 46 | `test_deadline_pressure_forces_run_on_tick[ppo]` | PASSED |
| 47 | `test_high_carbon_waits_without_deadline[greedy]` | PASSED |
| 48 | `test_high_carbon_waits_without_deadline[ppo]` | PASSED |

### `test_persistent_store.py` (3)

| # | Test name | Status |
|---:|---|---|
| 49 | `test_create_job_has_job_type_and_duration_fields` | PASSED |
| 50 | `test_fresh_db_per_test` | PASSED |
| 51 | `test_profile_seeded` | PASSED |

### `test_ppo_and_benchmark.py` (5)

| # | Test name | Status |
|---:|---|---|
| 52 | `test_ppo_without_model_uses_fallback` | PASSED |
| 53 | `test_ppo_waits_at_high_carbon_without_deadline` | PASSED |
| 54 | `test_ppo_force_run_on_critical_deadline` | PASSED |
| 55 | `test_state_to_obs_shape` | PASSED |
| 56 | `test_benchmark_runs` | PASSED |

## 5. Why nothing is failing

Nothing fails because the two root causes behind the bad PPO result are fixed:

1. **Wrong dataset path.** `ComparisonService` used `Path(__file__).resolve().parents[2]`,
   which from `backend/app/application/` resolves to `backend/`, not the project root. It
   therefore looked for `backend/simulator/data/snapshots_2026-02-10_IN-2025-5_minute.csv`,
   which does not exist. It now resolves to the top-level
   `simulator/data/snapshots_2026-02-10_IN-2025-5_minute.csv` (a real 10 MB CSV), exposed as
   `DEFAULT_CARBON_DATASET_PATH` in `backend/app/application/comparison_service.py`.
2. **Silent random fallback.** `load_carbon_csv` in `simulator/benchmark.py` returned 5,000
   pseudo-random values (uniform 329–706) whenever the path was missing, unreadable, empty or
   column-less, so a broken path produced plausible-looking but meaningless numbers. It now
   raises `FileNotFoundError` (missing file) or `ValueError` (unusable file).

Verified end to end at horizon 2000 / seed 42 on the real CSV:

| Policy | Completed | Failed | Deadline misses | Carbon (g) | Avg intensity |
|---|---:|---:|---:|---:|---:|
| Greedy | 37 | 0 | 0 | 2.96 | 519.2 |
| Forecast | 36 | 0 | 2 | 2.87 | 512.0 |
| Constraint Lexicographic | 39 | 0 | 0 | 3.28 | 546.0 |
| PPO | 39 | 0 | 0 | 3.40 | 566.4 |

## 6. The 7 new regression tests: what they guard and why they failed before

All 7 are in `backend/tests/test_comparison_support.py`. I re-ran the pre-fix code in a
throwaway `git worktree` of `HEAD` to confirm each one genuinely fails without the fix.

| Test | Guards | Pre-fix failure reason |
|---|---|---|
| `test_comparison_service_uses_top_level_simulator_dataset` | Path is the project-root `simulator/data` file and it exists | `PROJECT_ROOT`/`DEFAULT_CARBON_DATASET_PATH` did not exist as module constants; the service pointed at `backend/simulator/data/…`, which is absent |
| `test_comparison_service_does_not_look_for_dataset_under_backend` | The old wrong location is not used | Old code built exactly that path; the guard pins the fact that only the top-level copy may be read |
| `test_carbon_loader_reads_real_dataset_instead_of_random_fallback` | Loader returns the real series, not 5,000 random values | `load_carbon_csv` returned `len=5000, min=329.1, max=705.8` (the synthetic fallback) instead of the real 17,520-point series |
| `test_carbon_loader_raises_instead_of_returning_random_data` | Missing dataset is an error | `pytest.raises(FileNotFoundError)` failed — the old loader returned a random array, so a missing file was invisible |
| `test_carbon_loader_raises_on_dataset_without_carbon_column` | Malformed dataset is an error | Old loader silently fell back to random values instead of raising `ValueError` |
| `test_comparison_service_run_reports_missing_dataset` | Service surfaces a missing dataset | Old `ComparisonService.__init__()` took no `carbon_dataset_path` argument, so this raised `TypeError: unexpected keyword argument` instead of `FileNotFoundError` |
| `test_comparison_service_run_records_real_dataset_path` | A recorded run really used the real CSV | Pre-fix run recorded `config.dataset = …/green-ai-scheduler/backend/simulator/data/snapshots_….csv`, which `exists() == False` |

## 7. Warnings (not failures)

The 116 warnings are deprecations, not test problems, and do not affect pass/fail:

| Source | Count | Note |
|---|---:|---|
| `app/application/job_orchestrator.py` (lines 105, 162, 254, 264) | 104 | `datetime.utcnow()` is deprecated in Python 3.14; replace with `datetime.now(datetime.UTC)` |
| `codecarbon/emissions_tracker.py` | 15 | `save_to_*` args deprecated; use `output_methods=[...]` |
| `sqlalchemy/sql/schema.py` | 1 | SQLAlchemy internal `datetime.utcnow()` deprecation |
| `backend/tests/test_orchestrator.py:247` | 12 | Test itself uses `datetime.utcnow()` |

Two of these are in code this project owns (`job_orchestrator.py` and the test at
`test_orchestrator.py:247`) and can be cleaned up, but that is unrelated to the dataset-path
bug and was left alone.

## 8. Known issues not covered by tests

- `backend/app/config.py:6` has the same `parents[2]` off-by-one as the old
  `ComparisonService`, so `_ENV_FILE` points at a nonexistent `backend/.env`. The API key is
  only picked up when the process cwd is `green-ai-scheduler/`. There is no test asserting
  the resolved `.env` location.
- No test exercises the HTTP endpoints in `backend/app/api/main.py` directly (including the new
  `503` for a missing dataset) — `test_api.py` only defines a `client` fixture.
- `backend/simulator/logs/comparison_results.json` still contains 6 stored runs produced from
  the old random fallback data. They are stale artefacts, not test failures.
