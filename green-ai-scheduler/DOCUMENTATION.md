# Green Hours Scheduler — Technical Documentation

This document explains what was built, how the architecture works, where real vs simulated data is used, how Greedy and PPO compare, known issues, and how the offline simulator fits in.

For setup commands, see [README.md](README.md).  
**End-to-end run process:** [RUNBOOK.md](RUNBOOK.md) — setup → post jobs → dashboard → PPO → benchmark.  
**What changed / what's missing:** [CHANGELOG.md](CHANGELOG.md).  
For capstone report bullet points, see [REPORT.md](REPORT.md).

---

## Problem statement — what is done vs missing

This table maps the **faculty problem statement (PS)** to this implementation. Use it directly in your capstone report scope section.

| PS requirement | Status | Where in this project | Notes |
|----------------|--------|----------------------|-------|
| Reduce carbon footprint via intelligent scheduling | **Done** | Greedy + PPO policies, pause/resume, `/stats` carbon saved | Core deliverable |
| Schedule during high renewable / clean grid periods | **Done** (with substitution) | `CarbonEstimator`, Electricity Maps API + CSV | Uses **carbon intensity (gCO₂/kWh)**, not renewable % — see [REPORT.md](REPORT.md) |
| **Deadline** constraints | **Done** | `GreedyPolicy` deadline-proximity RUN-forcing; PPO force-RUN near deadline | See [status_machine.md](backend/docs/status_machine.md) |
| **Performance** constraints | **Done** | `performance_target` = min-epoch floor before carbon-aware pause | Enforced in Greedy; safety override in PPO |
| **Cost** constraints | **Not done** (documented descope) | README, REPORT, §1 below | Intentional milestone cut — state this plainly to faculty |
| Active scheduling (not just measurement) | **Done** | `JobOrchestrator` tick loop, not measure-only like CodeCarbon alone | |
| Real ML model training (ResNet / BERT) | **Done** (live jobs) | `jobs/resnet50_cifar.py`, `jobs/bert_imdb.py`, `registry.py` | Benchmark still uses synthetic jobs for speed |
| Measured emissions via CodeCarbon | **Done** (live sessions) | `jobs/carbon_session.py` | Fallback estimate if tracker fails |
| Multi-node / cluster placement | **Not in scope** | Single machine, one `RUNNING` job max | By design |
| India national grid | **Done** (limitation noted) | Zone `IN`; CSV is Mainland India average | Not city-specific |

**Summary for evaluators:** The PS is **substantially met** on carbon-aware scheduling, deadlines, and training-progress constraints. **Cost optimization is the main explicit PS gap** — documented as scope, not an oversight. **Real PyTorch training workloads** are the main technical gap vs the original spec wording (ResNet/BERT job types).

---

## 1. What this project does

**Green Hours Scheduling** is a **carbon-aware ML job scheduler** for a **single machine** (not Kubernetes / multi-node). It answers one question:

> *When should this training job run, pause, or resume, given how clean the electricity grid is right now?*

It does **not** decide which server or cluster node to use. At most **one job runs at a time**.

### What was implemented

| Layer | Components | Status |
|-------|------------|--------|
| **Infrastructure** | `PersistentJobStore` (SQLite + WAL), `ExecutionEngine` (thread pool + cooperative pause) | Complete |
| **Intelligence** | `CarbonEstimator`, `GaiQEngine`, `GreedyPolicy`, `PPOPolicy` | Complete |
| **Application** | `JobOrchestrator` (60s tick loop, status machine, profile refinement) | Complete |
| **API** | FastAPI: jobs, pause/resume, grid status, stats, bulk submit | Complete |
| **Frontend** | React dashboard, Greedy/PPO toggle, batch job submit | Complete |
| **Simulator** | Offline PPO training + Greedy vs PPO benchmark | Complete |
| **Tests** | 36 pytest tests (unit, integration, policy-parametric) | Passing |

### What was intentionally not implemented

- **Cost optimization** — descoped; documented in README/REPORT
- **Real ResNet50 / BERT training** — job types exist in the schema but all jobs currently run the same simulated training loop (see §5)
- **CodeCarbon live tracking** — energy/carbon on live jobs uses a simplified power×duration estimate, not a full CodeCarbon session wrapper
- **Multi-node / Kubernetes scheduling** — out of scope

---

## 2. Architecture

### Layer diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)                                     │
│  Polls /jobs, /stats, /grid/status every 10s                 │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP
┌───────────────────────────▼─────────────────────────────────┐
│  API (FastAPI)                                               │
│  Only talks to JobOrchestrator — never skips to lower layers │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  JobOrchestrator (Application)                               │
│  • Scheduling tick (default 60s)                             │
│  • Status machine (QUEUED → WAITING → RUNNING → PAUSED …)   │
│  • Sole writer to PersistentJobStore                         │
│  • Receives session reports from ExecutionEngine             │
└───────┬───────────────────────────────┬─────────────────────┘
        │                               │
        ▼                               ▼
┌───────────────────┐         ┌─────────────────────────────┐
│  Intelligence      │         │  Infrastructure              │
│  • CarbonEstimator │         │  • PersistentJobStore (SQLite)│
│  • GaiQEngine      │         │  • ExecutionEngine (1 worker) │
│  • DecisionEngine  │         └─────────────────────────────┘
│    └ GreedyPolicy  │
│    └ PPOPolicy     │
└───────────────────┘

ExecutionEngine ──session report──► JobOrchestrator (never writes DB directly)
Intelligence ──pure functions──► returns data only (never writes DB)
```

### Dependency rules (important)

1. **API → JobOrchestrator only** — including read-only routes like `/grid/status`
2. **Intelligence never calls Infrastructure** — `GaiQEngine` takes profile data in, returns updated profile out; `JobOrchestrator` persists it
3. **ExecutionEngine reports, never writes** — carbon/energy/epoch updates happen in `JobOrchestrator` after each session
4. **Single-flight** — `decide()` is called **at most once per tick** on **at most one job**; `ThreadPoolExecutor(max_workers=1)` enforces one running training session

### Job status machine

| Status | Meaning |
|--------|---------|
| `QUEUED` | Just submitted (`POST /jobs`) |
| `WAITING` | Scheduler decided to wait for cleaner grid |
| `RUNNING` | Training session active in worker thread |
| `PAUSED` | System paused (high carbon); auto-resumable on next tick |
| `MANUALLY_PAUSED` | User paused; **never** auto-resumed until `POST /jobs/{id}/resume` |
| `COMPLETED` | All epochs finished |
| `FAILED` | Error or deadline missed |

See also [backend/docs/status_machine.md](backend/docs/status_machine.md).

---

## 3. Greedy vs PPO — which to use where

### GreedyPolicy (primary, recommended default)

**How it works:** Hand-tuned thresholds.

- **Start / resume** when carbon intensity &lt; `run_threshold` (default 450 gCO₂/kWh)
- **Pause** when intensity &gt; `pause_threshold` (default 550 gCO₂/kWh) — hysteresis prevents thrashing
- **Force RUN** when: deadline is close, `pause_count` at max, or `current_epoch < performance_target`

| Use Greedy when… | Why |
|------------------|-----|
| Live demo / dashboard | Deterministic, explainable, always works |
| Capstone presentation | Easy to describe: "wait for green hours" |
| Production default | No trained model file required |
| Tests | Ground-truth scheduling behavior |

### PPOPolicy (learned, optional)

**How it works:** A small reinforcement-learning model (`stable-baselines3` PPO) trained offline on historical carbon data. It outputs `RUN`, `WAIT`, or `PAUSE` from an 8-dimensional state vector.

| Use PPO when… | Why |
|---------------|-----|
| Report / research comparison | Show learned policy vs rule-based baseline |
| Offline benchmark | `simulator/benchmark.py` compares both on same episodes |
| Dashboard experiment | Toggle PPO tab after training `simulator/models/ppo_scheduler.zip` |

### Fallback behavior

| Situation | What runs |
|-----------|-----------|
| PPO model file **missing** | `PPOPolicy` delegates to **GreedyPolicy** |
| PPO model **loaded** but constraints violated | **Force RUN** for deadline, performance floor, max pauses (same safety rules as Greedy) |
| No API key in `.env` | `CarbonEstimator` uses **mock** 500 gCO₂/kWh |
| CSV missing for simulator | **Synthetic** random carbon series (329–706 range) |

**Recommendation:** Use **Greedy** for the live demo and report it as the primary deliverable. Use **PPO** as a secondary comparison after running `train_ppo` + `benchmark`.

---

## 4. Real vs simulated — complete map

### Carbon / grid data

| Data | Real or simulated? | Source |
|------|-------------------|--------|
| Live grid intensity (dashboard `/grid/status`) | **Real** (if API key set) | Electricity Maps API, zone `IN` |
| Live grid intensity (no API key) | **Mock** | Fixed 500 gCO₂/kWh |
| PPO training & benchmark timeline | **Real** | `snapshots_2026-02-10_IN-2025-5_minute.csv` (India 2025, 5-min) |
| CSV missing | **Synthetic** | Random uniform 329–706 gCO₂/kWh |

### Job execution (live system)

| Component | Real or simulated? | Details |
|-----------|-------------------|---------|
| All job types (`simulated`, `resnet50_cifar`, `bert_imdb`) | **Simulated training** | Every job runs `run_simulated_job()` — sleep loop + fake loss, no real neural network |
| Epoch counter | **Real counter** | Increments per simulated epoch; checkpoint saved to disk |
| `carbon_used_g` / `energy_used_kwh` | **Estimated** | `power_kw × duration_hours` and `energy × ~500 g/kWh` — not CodeCarbon hardware measurement |
| `baseline_carbon_estimate_g` | **Real formula** | GaiQ: `expected_power × expected_duration × grid_intensity` at submit time |
| GaiQ grade (A–D) | **Real math** | Derived from `carbon_used_g / baseline_carbon_estimate_g` |
| Profile refinement | **Real rolling average** | After job completes, from measured `energy_used_kwh / total_duration_hours` |

**Important:** Job type names (`resnet50_cifar`, `bert_imdb`) affect **profile seeds** and sleep timing only — they do **not** load torchvision or Hugging Face models today.

### Offline benchmark (`simulator/benchmark.py`)

| Component | Real or simulated? |
|-----------|-------------------|
| Carbon intensity series | **Real** (from CSV validation months) |
| Job arrivals | **Synthetic** (Poisson process, fixed seed 42) |
| Job execution | **Synthetic** (tick-based epoch increments) |
| Carbon per epoch | **Formula** (`0.05 × intensity / 500` grams) |
| `baseline_carbon_g` per job | **Random placeholder** (40–60 g) |
| Policy decisions | **Real** (actual Greedy / PPOPolicy code) |

**Do not** interpret benchmark `carbon_saved_g: ~1835` as kilograms of real CO₂ saved. It is valid for **relative** Greedy vs PPO comparison only.

### PPO training (`simulator/train_ppo.py`)

| Component | Real or simulated? |
|-----------|-------------------|
| Carbon timeline | **Real** (CSV train split, first 10 months) |
| Gym environment | **Simplified** scheduler simulator |
| Learned model | **Real** PPO weights saved to `simulator/models/ppo_scheduler.zip` |

---

## 5. How the live simulation (`run_simulated_job`) works

When the orchestrator dispatches a job:

1. A **worker thread** runs `run_simulated_job` (blocking work off the asyncio event loop).
2. Each **epoch** = 10 **batches**; each batch sleeps briefly and multiplies a fake `loss` by 0.95.
3. A **cancel event** is checked every batch — cooperative pause for system/manual pause.
4. On pause or complete, a PyTorch checkpoint `{epoch, loss}` is saved.
5. **Session report** sent to orchestrator: carbon, energy, duration, epoch reached.
6. Orchestrator **accumulates** `carbon_used_g += session`, `energy_used_kwh += session`, updates status.

This is why the dashboard shows believable epoch progress and carbon saved at a **small scale** (milligrams to grams), but **no model weights are trained**.

---

## 6. How the offline benchmark simulation works

```
CSV (real carbon) ──► SchedulingSimulator
                           │
         Poisson job arrivals (synthetic, seed=42)
                           │
              For each tick (2000 default):
                1. Pick one candidate job (single-flight)
                2. policy.decide(state)
                3. RUN → start/continue; WAIT/PAUSE → wait or pause
                4. Increment epochs, accumulate formula carbon
                5. Check deadlines
                           │
              Metrics: jobs_completed, carbon_saved, pause_count, …
```

Run:

```bash
cd backend
PYTHONPATH=.:.. python -m simulator.benchmark --policies greedy,ppo
```

Output is printed and saved to `simulator/logs/benchmark_results.json`.

---

## 7. Issues encountered and fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| PPO training crash (`obs[3]` out of bounds) | Negative wait time for future-arrival jobs | Clip observations to [0,1]; filter jobs not yet arrived |
| PPO benchmark 0 jobs completed | Model learned "never start" (always WAIT when idle) | Added force-RUN safety rules; improved training rewards |
| Greedy = PPO identical benchmark | No trained model → PPO fell back to Greedy | Train with `python -m simulator.train_ppo` first |
| `deadline_misses: 30427` | Counted every tick after deadline, not once per job | Count each job's miss only once |
| `.env` not loading | Wrong variable name (`ELECTRICITY_MAP_API`) and wrong cwd | Renamed to `ELECTRICITY_MAPS_API_KEY`; config resolves project-root `.env` |
| CSV not found by simulator | File at repo root, not `simulator/data/` | Symlink placed at expected path |
| `GET /` returned 404 | No root route | Added `/` with links to `/docs` |
| Gym deprecation warning | `stable-baselines3` pulls old `gym` | Harmless; training uses `gymnasium` in our env |

---

## 8. Configuration reference

### `.env` (project root: `green-ai-scheduler/.env`)

```env
ELECTRICITY_MAPS_API_KEY=your_key_here
ELECTRICITY_MAPS_ZONE=IN
```

### Key defaults (`backend/app/config.py`)

| Setting | Default | Purpose |
|---------|---------|---------|
| `greedy_run_threshold` | 450 | Start when intensity below this |
| `greedy_pause_threshold` | 550 | Pause when intensity above this |
| `tick_interval_seconds` | 60 | Scheduler tick period |
| `ppo_model_path` | `../simulator/models/ppo_scheduler.zip` | Trained PPO weights |

Faster demos: `TICK_INTERVAL_SECONDS=5 uvicorn app.api.main:app --reload --port 8000`

---

## 9. API quick reference

| Endpoint | Purpose |
|----------|---------|
| `POST /jobs` | Submit one job |
| `POST /jobs/bulk` | Submit N jobs (`count`, `name_prefix`, `job_type`, …) |
| `GET /jobs` | List all jobs |
| `POST /jobs/{id}/pause` | Manual pause → `MANUALLY_PAUSED` |
| `POST /jobs/{id}/resume` | Resume manual pause → `QUEUED` |
| `GET /grid/status` | Current carbon intensity |
| `GET /stats?policy=greedy\|ppo` | Queue stats + switch active policy |

---

## 10. Testing strategy

- **36 pytest tests** — store, execution engine, policies, orchestrator, API
- **Parametric `@pytest.fixture(params=["greedy", "ppo"])`** — same scheduling invariants for both policies
- **Offline benchmark** — policy outcome comparison on held-out carbon months

```bash
cd backend
PYTHONPATH=.:.. pytest -v
```

---

## 11. Honest summary for evaluators

| Claim | Accurate? |
|-------|-----------|
| "We schedule training based on live grid carbon" | **Yes** (with Electricity Maps API) |
| "We compare Greedy and PPO scheduling policies" | **Yes** |
| "We pause and resume with checkpointing" | **Yes** (simulated training loop) |
| "We train ResNet50 on CIFAR-10" | **No** — job type label only; execution is simulated |
| "Benchmark saved 1.8 kg CO₂" | **No** — offline metric uses simplified accounting |
| "PPO is production-ready" | **Partial** — needs more training/tuning; Greedy is the reliable baseline |

---

## 12. Suggested next steps (not yet done)

1. Wire `run_resnet_job()` / `run_bert_job()` with real PyTorch + CodeCarbon
2. Replace estimated carbon with CodeCarbon `EmissionsTracker` per session
3. Train PPO longer / tune rewards; optional `MaskablePPO` for valid actions only
4. Add job submission UI polish and GaiQ grade on dashboard cards

---

## File map

```
green-ai-scheduler/
├── DOCUMENTATION.md          ← this file
├── README.md                 ← setup & run commands
├── REPORT.md                 ← capstone report notes
├── .env                      ← API keys (not committed)
├── snapshots_…csv            ← carbon dataset (user-provided)
├── backend/app/
│   ├── api/                  ← FastAPI routes
│   ├── application/          ← JobOrchestrator
│   ├── intelligence/         ← Carbon, GaiQ, Greedy, PPO
│   └── infrastructure/       ← SQLite store, ExecutionEngine
├── frontend/                 ← React dashboard
└── simulator/
    ├── train_ppo.py          ← offline PPO training
    ├── benchmark.py          ← Greedy vs PPO comparison
    ├── data/                 ← CSV symlink / copy
    └── models/               ← ppo_scheduler.zip (after training)
```
