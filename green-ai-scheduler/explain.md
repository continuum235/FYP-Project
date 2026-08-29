# Green Hours Scheduler — Detailed Project Explanation

Read this document to understand the project end-to-end and to explain it clearly in a viva, demo, or report presentation. It is written in plain language: what we built, why we built it, how it works, and what to say when someone asks hard questions.

---

## 1. What is this project? (30-second pitch)

**Green Hours Scheduler** is a carbon-aware job scheduler for machine learning training on **one computer**.

Instead of training continuously and ignoring the electricity grid, our system asks:

> *“Given how dirty the grid is right now — and how soon this job must finish — should we **run**, **wait**, or **pause** training?”*

We built a **full working system**: live carbon data from India’s grid, a backend that schedules jobs, a web dashboard, two scheduling policies (**Greedy** and **PPO**), real PyTorch training paths (ResNet, BERT), and an offline benchmark to compare policies fairly.

**One line for externals:**  
*“CodeCarbon measures emissions; we **schedule** when training runs to reduce them.”*

> **Reading tip:** Sections 1–16 explain *what* and *why*. **Section 17** is the **code walkthrough** — file paths, line references, and snippets you can open in the IDE (`Ctrl+P` / `Cmd+P` to jump to a file; `Ctrl+G` / `Cmd+G` for a line number).

---

## 2. What problem are we solving?

### The real-world issue

Training AI models uses a lot of electricity. That electricity is **not equally clean all day**:

- Midday may be cleaner (more solar).
- Evening peaks may be dirtier (more coal/gas).
- Carbon intensity is measured in **gCO₂/kWh** (grams of CO₂ per kilowatt-hour).

Most training scripts **start immediately** and run until done. That wastes the chance to shift work to greener hours.

### What existing tools do NOT do

| Tool | What it does | What it does NOT do |
|------|--------------|---------------------|
| **CodeCarbon** | Measures CO₂ during a run | Does not pause/resume based on grid |
| **Kubernetes / SLURM** | Allocates CPU/GPU | Does not care about carbon |
| **Electricity Maps** | Shows grid intensity | Does not control your training |

**Our gap:** Active scheduling — **when** to train — while respecting **deadlines** and **training progress**.

### What we deliberately do NOT solve (scope)

- **Multi-datacenter placement** (“run in region A vs B”) — out of scope; we schedule **in time** on one machine.
- **Autoscaling** (spin up more GPUs) — not implemented.
- **Cost optimization** (electricity bills) — documented descope.
- **Cluster scheduling** — single node, one running job at a time by design.

---

## 3. High-level solution

```text
User submits ML training job
        ↓
Job enters queue (QUEUED)
        ↓
Every N seconds, orchestrator "tick":
  - Fetches live carbon intensity (+ forecast)
  - Builds state (deadline, progress, queue, etc.)
  - Greedy OR PPO decides: RUN / WAIT / PAUSE
        ↓
Execution engine runs training (or pauses cooperatively)
        ↓
CodeCarbon records carbon per session
        ↓
Job completes → stats update on dashboard
```

**Two policies, one orchestrator:**

| Policy | Type | When to use |
|--------|------|-------------|
| **Greedy** | Rule-based (thresholds) | Live demo, explainability, production default |
| **PPO** | Learned (reinforcement learning) | Research comparison, offline benchmark |

You **select** Greedy or PPO on the dashboard. They are **not merged** into one algorithm every tick.

---

## 4. System architecture (four layers)

```text
┌─────────────────────────────────────────────────────────┐
│  PRESENTATION: React dashboard (localhost:5173)         │
│  - Carbon intensity, job list, Greedy/PPO toggle        │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTP
┌───────────────────────────▼─────────────────────────────┐
│  API: FastAPI (localhost:8000)                          │
│  - POST /jobs, GET /stats, GET /grid/status             │
│  - Only talks to JobOrchestrator                        │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  APPLICATION: JobOrchestrator                           │
│  - Tick loop (default 60s; demo: 5–10s)                 │
│  - Status machine: QUEUED → WAITING → RUNNING → …       │
│  - Sole writer to database                              │
└───────┬───────────────────────────────────────┬─────────┘
        │                                       │
┌───────▼──────────────┐              ┌─────────▼──────────┐
│  INTELLIGENCE        │              │  INFRASTRUCTURE     │
│  - CarbonEstimator   │              │  - SQLite JobStore  │
│  - GaiQEngine        │              │  - ExecutionEngine  │
│  - GreedyPolicy      │              │  - Training jobs    │
│  - PPOPolicy         │              │    (sim/ResNet/BERT)│
│  - must_force_run()  │              │  - CodeCarbon wrap  │
└──────────────────────┘              └────────────────────┘
```

### Why this layering matters (viva answer)

- **Intelligence never writes to the database directly** — only the orchestrator does. That keeps scheduling logic testable and avoids race bugs.
- **API never calls Greedy/PPO directly** — always through the orchestrator.
- **Execution engine** runs training in a background thread; scheduling decisions happen on the tick.

---

## 5. How scheduling decisions work

### 5.1 The three actions

| Action | Meaning (job not running) | Meaning (job running) |
|--------|---------------------------|------------------------|
| **RUN** | Start or resume training | Keep training |
| **WAIT** | Stay in queue; do not start | (Orchestrator may request pause) |
| **PAUSE** | N/A for queued jobs | Stop cooperatively; save checkpoint |

### 5.2 Greedy policy (India-tuned thresholds)

Greedy is a **simple, explainable** rule-based policy:

| Carbon intensity | Queued job | Running job |
|------------------|------------|-------------|
| **< 550 gCO₂/kWh** | RUN | Keep running |
| **550 – 700** | WAIT (hold band) | Keep running (hysteresis) |
| **> 700 gCO₂/kWh** | WAIT | PAUSE |

**Why hysteresis (550 vs 700)?**  
Prevents flip-flopping. If you used one threshold, the job would pause and resume every few minutes as carbon wiggles.

**Force RUN (overrides carbon):**

- Deadline is close (`_deadline_pressure` estimates if not enough time left).
- Max pause count reached.
- Critical deadline window (`must_force_run`).

### 5.3 PPO policy (constraint-augmented)

PPO is a **neural network** trained offline on historical India carbon data.

**Before** the network decides:

```text
if deadline critical OR max pauses exhausted:
    → force RUN   (safety — same as shared constraints)
else:
    → PPO predicts RUN / WAIT / PAUSE from 12-dim state
```

**State includes:** current carbon, forecast avg/min, time to clean window, deadline slack, queue length, training progress, pause count, priority, etc.

**If model file is missing:** PPO falls back to Greedy.

**Important:** We call this **constraint-augmented PPO**, not “Hybrid Constrained PPO.” The system is a **dual-policy framework** (Greedy + constrained PPO), not one fused algorithm.

**See code:** `backend/app/intelligence/policies/greedy.py` (thresholds), `backend/app/intelligence/policies/ppo_policy.py` (12-dim obs + `decide`), `backend/app/intelligence/constraints.py` (shared hard rules) — full snippets in **§17**.

### 5.4 Hard vs soft constraints

| Constraint | Type | How enforced |
|------------|------|--------------|
| Critical deadline | **Hard** | `must_force_run()` → RUN |
| Max pauses | **Hard** | `must_force_run()` → RUN |
| Greedy deadline pressure | **Hard** (Greedy only) | `_deadline_pressure()` → RUN |
| Training progress (`performance_target`) | **Soft** | PPO reward penalty; not a force-RUN override |

---

## 6. Job lifecycle (status machine)

```text
QUEUED ──(tick: WAIT)──► WAITING
QUEUED ──(tick: RUN)───► RUNNING ──(pause)──► PAUSED
RUNNING ──(complete)───► COMPLETED
RUNNING ──(error)──────► FAILED
Any ──(user pause)─────► MANUALLY_PAUSED  (never auto-resumed)
```

**Single-flight rule:** At most **one job RUNNING** at a time. The orchestrator evaluates **one job per tick** (running job first, else highest-priority queued job).

**Cooperative pause:** Training loops check a cancel flag every batch. On pause, we save checkpoint (epoch, weights) and resume later.

---

## 7. Carbon data: live vs historical

### Live (dashboard / real scheduling)

- **Source:** Electricity Maps API, zone **IN** (India).
- **Config:** `.env` → `ELECTRICITY_MAPS_API_KEY`, `ELECTRICITY_MAPS_ZONE=IN`
- **Typical reading:** ~500–700 gCO₂/kWh depending on time of day.

### Offline (PPO training + benchmark)

- **Source:** CSV snapshots (`simulator/data/…csv`), five-minute resolution.
- **Train:** First ~10 months of data.
- **Benchmark:** Held-out last ~2 months (fair evaluation).

**Note:** We use **carbon intensity**, not “renewable percentage.” Faculty problem statements sometimes mention renewables; intensity is what the API provides and what is actionable for pause/resume.

---

## 8. GaiQ and carbon saved

### GaiQEngine

At **job submission**, we estimate a **baseline carbon** — “how much CO₂ this job would use if it ran naively” — using:

- Job type profile (expected power × duration).
- Current (or forecast-averaged) grid intensity.

After completion, profiles refine from actual measured power and duration.

### `total_carbon_saved_g` on dashboard

```text
For each COMPLETED job:
  saved = max(0, baseline_carbon_estimate_g - carbon_used_g)

Dashboard total = sum of saved over completed jobs only
```

**Why it might show 0:**

- Waiting/running jobs **do not count** until COMPLETED.
- If **actual carbon ≥ baseline** (e.g. CodeCarbon measures full machine power but baseline assumes small simulated profile), saved = 0 for that job.
- This is a **metric quirk**, not proof scheduling failed.

**Offline benchmark `carbon_saved_g` (~1800–1950)** is a **different scale** — synthetic jobs, relative comparison only. Do not compare directly to live dashboard grams.

---

## 9. Greedy vs PPO — why compare them?

| Research reason | Explanation |
|-----------------|-------------|
| **Baseline requirement** | Every RL paper needs a simple opponent. Greedy is ours. |
| **Interpretability** | Greedy: “below 550 run, above 700 pause.” Easy for faculty. |
| **Fair test** | Same carbon CSV, same random seed, same synthetic jobs. |
| **Honest science** | PPO lost at 50k training steps; **won after 200k steps**. |

### Latest offline benchmark (identical conditions)

| Metric | Greedy | PPO (200k training) |
|--------|--------|---------------------|
| Jobs completed | 37 | **39** |
| Deadline misses | 0 | **0** |
| Carbon saved (relative) | ~1839 g | **~1950 g** |
| Clean-window finishes | **24** | 6 |

**How to explain:**  
Greedy finishes more jobs in explicitly “clean” windows (threshold-based). PPO completes more jobs overall with zero deadline misses after sufficient training — learned deferral vs fixed rules.

---

## 10. What is real vs simulated?

| Component | Real? | Notes |
|-----------|-------|-------|
| Electricity Maps API | **Yes** | Live carbon on dashboard |
| Scheduler / API / DB | **Yes** | Full stack |
| Greedy / PPO logic | **Yes** | Same code live and offline |
| **Simulated jobs** | Fast demo | ~4.5s per job; for tests/demo |
| **ResNet50 / BERT** | **Yes** | Real PyTorch; slower; downloads data once |
| Offline benchmark jobs | **Synthetic** | Poisson arrivals; not your dashboard jobs |
| Benchmark carbon_saved ~1800g | **Relative** | Policy comparison only |

**Demo tip:** Use **simulated jobs** + **Greedy** + `TICK_INTERVAL_SECONDS=5` for a visible WAIT/PAUSE demo at high carbon.

---

## 11. How to run and demo

### Start system

```bash
# Terminal 1 — backend
cd green-ai-scheduler/backend
export TICK_INTERVAL_SECONDS=5
PYTHONPATH=. uvicorn app.api.main:app --reload --port 8000

# Terminal 2 — frontend
cd green-ai-scheduler/frontend
npm run dev
# Open http://localhost:5173
```

### Train PPO (offline)

```bash
cd green-ai-scheduler
PYTHONPATH=backend:. python -m simulator.train_ppo
# ~4–5 min for 200k steps → saves simulator/models/ppo_scheduler.zip
# Restart backend after training to load new model
```

### Run benchmark (offline)

```bash
cd green-ai-scheduler
PYTHONPATH=backend:. python -m simulator.benchmark --policies greedy,ppo --horizon 2000
```

**Benchmark does NOT update live dashboard stats.** It prints JSON and saves `simulator/logs/benchmark_results.json`.

### Suggested 10-minute demo script

1. Show live carbon intensity (~600+ gCO₂/kWh).
2. Select **Greedy**, submit 5 simulated jobs → show **WAITING** at high carbon.
3. Explain thresholds: 550 run, 700 pause, hold band between.
4. Submit one job with **deadline in 2 minutes** → show it **runs** despite high carbon (deadline override).
5. Switch to **PPO**, mention offline benchmark results.
6. Show `GET /stats` and `GET /jobs` — completed count, carbon fields.

---

## 12. Project structure (what each part does)

```text
green-ai-scheduler/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routes
│   │   ├── application/      # JobOrchestrator (heart of system)
│   │   ├── intelligence/     # Greedy, PPO, carbon, GaiQ, constraints
│   │   ├── infrastructure/   # DB, execution engine, training jobs
│   │   └── domain/           # Models, enums
│   └── tests/                # 41+ pytest tests
├── frontend/                 # React dashboard
├── simulator/
│   ├── train_ppo.py          # Offline PPO training
│   ├── benchmark.py          # Greedy vs PPO comparison
│   ├── models/ppo_scheduler.zip
│   └── data/                 # India carbon CSV
├── explain.md                # This file
├── RESEARCH_PAPER.md         # Paper draft
├── DOCUMENTATION.md          # Technical deep-dive
├── DEMO_GUIDE.md             # Viva Q&A (40+ questions)
└── RUNBOOK.md                # Commands cheat sheet
```

---

## 13. Literature connection (your 8 references)

| Reference | Idea | Our implementation |
|-----------|------|-------------------|
| Schwartz (2020) | Red AI vs Green AI | Practical load shifting |
| Sikand (2023) | GaiQ metrics | GaiQEngine + dashboard |
| Chitakunye (2025) | Model switching | Carbon-triggered run/pause; job types |
| Sreedhar Radhakrishnan (2024) | PPO for carbon | PPOPolicy, offline training |
| Weng & Li (2024) | Greedy short-sighted | Greedy baseline vs PPO |
| Yarally (2023) | End-to-end pipeline | Submit → schedule → train → measure |
| Aggarwal & Sharma (2025) | kWh → CO₂ | CodeCarbon + g per job |
| Chandran (2025) | Live benchmarking | Dashboard + benchmark.py |

---

## 14. Common questions and clear answers

### “Is this just a timer that waits for night?”

**No.** We use **real-time carbon intensity**, not clock time. Carbon at 2 PM today can differ from 2 PM tomorrow.

### “Why did jobs run at 605 gCO₂/kWh?”

With **old** settings, `performance_target` forced RUN. **Now:** without urgent deadline, jobs should **WAIT** in the hold band. With a **tight deadline**, force RUN is correct.

### “Why doesn’t benchmark match `/stats`?”

**Different systems.** Benchmark = fresh simulator run. `/stats` = cumulative SQLite history from jobs you submitted live.

### “Is PPO worse than Greedy?”

**Depends on training.** At 50k steps, yes. At **200k steps** on our benchmark, PPO wins on jobs completed and carbon saved.

### “Did you implement placement across regions?”

**No.** Temporal scheduling on one node. Paper-style placement is **future work**.

### “What is constraint-augmented PPO?”

Hard rules (deadline, max pause) run **before** the neural network. Safety is not left to RL alone.

### “What is NOT in scope?”

Cost optimization, Kubernetes, multi-region, autoscaling.

---

## 15. Problem statement alignment (honest checklist)

| Requirement | Status |
|-------------|--------|
| Carbon-aware scheduling | Done |
| Clean grid periods (via intensity) | Done |
| Deadline constraints | Done |
| Performance / training progress | Done (soft via reward) |
| Real ML training path | Done (ResNet, BERT) |
| Cost constraints | **Not done** (documented) |
| Multi-node placement | **Not done** (by design) |

**~85–90% of problem statement** — strong for final year with live demo.

---

## 16. Three sentences to memorize before viva

1. *“We schedule **when** ML training runs based on live grid carbon, using RUN, WAIT, and PAUSE — not **where** in the cloud.”*

2. *“**Greedy** is our explainable baseline; **constraint-augmented PPO** is our learned comparison, with hard deadline overrides before the neural network acts.”*

3. *“Offline benchmark on India carbon data shows PPO after 200k training beats Greedy on job completion and carbon savings; the live dashboard proves the same orchestrator runs on real submitted jobs.”*

---

## 17. Code walkthrough (files, snippets, navigation)

This section maps **concepts → source files** and shows the **actual code** behind the scheduler. Open any path relative to `green-ai-scheduler/`.

### 17.1 Master file map

| What you are explaining | File | Key lines |
|-------------------------|------|-----------|
| HTTP API (submit jobs, stats, grid) | `backend/app/api/main.py` | 32–80 |
| App startup, policy switch, PPO load | `backend/app/api/deps.py` | 20–78 |
| **Heart of system** — tick loop, dispatch | `backend/app/application/job_orchestrator.py` | 149–340 |
| Greedy vs PPO selection | `backend/app/intelligence/decision_engine.py` | 11–45 |
| India thresholds (550 / 700) | `backend/app/intelligence/defaults.py` | 1–4 |
| Shared hard constraints | `backend/app/intelligence/constraints.py` | 4–17 |
| Greedy RUN / WAIT / PAUSE rules | `backend/app/intelligence/policies/greedy.py` | 22–50 |
| PPO observation vector + decide | `backend/app/intelligence/policies/ppo_policy.py` | 26–108 |
| Forecast / clean-window helpers | `backend/app/intelligence/state_builder.py` | 7–31 |
| Job statuses & actions | `backend/app/domain/enums.py` | 4–23 |
| Training thread + cooperative pause | `backend/app/infrastructure/execution_engine.py` | 23–80 |
| Fast demo training loop | `backend/app/infrastructure/jobs/simulated.py` | 12–60 |
| React dashboard + policy toggle | `frontend/src/App.jsx` | 5–70 |
| Offline PPO training | `simulator/train_ppo.py` | (entire file) |
| Greedy vs PPO benchmark | `simulator/benchmark.py` | (entire file) |

### 17.2 End-to-end code path (one tick)

```text
frontend/src/App.jsx
  → POST /jobs/bulk          backend/app/api/main.py
  → orch.submit_job()        backend/app/application/job_orchestrator.py
  → (every TICK_INTERVAL) tick()
       → CarbonEstimator      backend/app/intelligence/carbon_estimator.py
       → _build_state()       job_orchestrator.py
       → decision.decide()    decision_engine.py → greedy.py OR ppo_policy.py
       → _dispatch_job()      → ExecutionEngine.run_job()
       → simulated.py / resnet / bert   (training in thread)
       → SessionReport        → _handle_session_report() → SQLite
```

### 17.3 Domain types — what the code names mean

Job statuses and scheduler actions are plain enums:

```python
# backend/app/domain/enums.py (lines 4–23)

class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    MANUALLY_PAUSED = "MANUALLY_PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Action(str, Enum):
    RUN = "RUN"
    WAIT = "WAIT"
    PAUSE = "PAUSE"
```

### 17.4 API layer — how the dashboard talks to the backend

```python
# backend/app/api/main.py (lines 32–36)

@app.post("/jobs", response_model=JobRead)
async def submit_job(payload: JobCreate) -> JobRead:
    orch = get_orchestrator(app)
    job = await orch.submit_job(payload)
    return JobRead.model_validate(job)
```

Policy switching does **not** recompile anything — it swaps the object inside `DecisionEngine`:

```python
# backend/app/api/deps.py (lines 31–41)

def switch_policy(app: FastAPI, name: str) -> None:
    orch: JobOrchestrator = app.state.orchestrator
    greedy = GreedyPolicy(...)
    ppo = _load_ppo()   # loads simulator/models/ppo_scheduler.zip if present
    policy = build_policy(name, greedy=greedy, ppo=ppo)
    orch._decision.set_policy(policy)
```

Frontend calls `GET /stats?policy=greedy` or `ppo` before submit so the backend switches policy:

```javascript
// frontend/src/App.jsx (lines 51–65)

const submitBatch = async () => {
  await fetch(`${API}/stats?policy=${policy}`)
  await fetch(`${API}/jobs/bulk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      count: Number(batchCount),
      job_type: 'simulated',
      total_epochs: 2,
      performance_target: null,   // demo: no soft force-RUN
    }),
  })
}
```

UI carbon colours use the **same 550 / 700 thresholds** as Greedy:

```javascript
// frontend/src/App.jsx (lines 5–8)

function carbonClass(intensity) {
  if (intensity < 550) return 'clean'
  if (intensity < 700) return 'moderate'
  return 'dirty'
}
```

### 17.5 Orchestrator tick — the scheduling loop

Every `TICK_INTERVAL_SECONDS` (default 60; demo 5), `_tick_loop` calls `tick()`:

```python
# backend/app/application/job_orchestrator.py (lines 214–250)

async def tick(self) -> None:
    # ... pick running job OR highest-priority queued job ...
    grid = await self._carbon.get_current_intensity()
    forecast = await self._carbon.get_forecast()
    state = self._build_state(job, grid.carbon_intensity_g_per_kwh, forecast, ...)
    action = self._decision.decide(state)

    if job.status == JobStatus.RUNNING:
        if action in (Action.WAIT, Action.PAUSE):
            await self._execution.request_pause(job.id)
        return

    if action == Action.RUN and not self._execution.is_busy:
        await self._dispatch_job(job)
    elif action == Action.WAIT:
        await self._store.update_job(job.id, status=JobStatus.WAITING)
```

`_build_state()` packs everything policies need (deadline, forecast, queue length, progress):

```python
# backend/app/application/job_orchestrator.py (lines 174–192)

return SchedulingState(
    is_currently_running=is_running,
    carbon_intensity=intensity,
    carbon_forecast=forecast,
    forecast_avg=f_avg,
    forecast_min=f_min,
    time_to_clean_window_hours=clean_window,
    time_to_deadline_hours=time_to_deadline,
    pause_count=job.pause_count,
    progress_ratio=prog,
    queue_length=queue_length,
    # ... priority, epochs, performance_target, etc.
)
```

### 17.6 Shared hard constraints (Greedy + PPO)

Both policies call the **same** function before applying their own logic:

```python
# backend/app/intelligence/constraints.py (lines 4–17)

def must_force_run(state: SchedulingState, *, deadline_critical_hours: float = 1.0) -> bool:
    if state.pause_count >= state.max_pause_count:
        return True
    if (
        state.time_to_deadline_hours is not None
        and state.time_to_deadline_hours <= deadline_critical_hours
    ):
        return True
    return False
```

Greedy adds **deadline pressure** on top (estimates if remaining work fits before deadline):

```python
# backend/app/intelligence/policies/greedy.py (lines 36–50)

def _force_run(self, state: SchedulingState) -> bool:
    return must_force_run(state) or self._deadline_pressure(state)

def decide(self, state: SchedulingState) -> Action:
    if self._force_run(state):
        return Action.RUN
    if state.is_currently_running:
        if state.carbon_intensity > self.pause_threshold:  # 700
            return Action.WAIT   # orchestrator maps WAIT on RUNNING → pause
        return Action.RUN
    if state.carbon_intensity < self.run_threshold:        # 550
        return Action.RUN
    return Action.WAIT
```

Default thresholds live in one place:

```python
# backend/app/intelligence/defaults.py

GREEDY_RUN_THRESHOLD = 550.0
GREEDY_PAUSE_THRESHOLD = 700.0
```

### 17.7 PPO — observation vector and constrained decide

The neural network sees **12 normalized features** (carbon, forecast, deadline, queue, …):

```python
# backend/app/intelligence/policies/ppo_policy.py (lines 55–72)

obs = np.array([
    float(state.is_currently_running),
    carbon_norm,
    forecast_avg_norm,
    forecast_min_norm,
    clean_window_norm,
    max(0.0, time_feature) / 24.0,
    deadline_norm,
    priority_norm,
    pause_ratio,
    perf_ratio,        # soft signal — NOT a hard force-RUN
    progress_ratio,
    queue_norm,
], dtype=np.float32)
```

`decide()` applies hard constraints **first**, then the model:

```python
# backend/app/intelligence/policies/ppo_policy.py (lines 91–108)

def decide(self, state: SchedulingState) -> Action:
    if self._model is None:
        return self._fallback.decide(state)          # Greedy if no .zip
    if must_force_run(state, deadline_critical_hours=self._deadline_critical_hours):
        return Action.RUN
    obs = state_to_obs(state)
    action_idx, _ = self._model.predict(obs, deterministic=True)
    action = self.ACTION_MAP.get(int(action_idx), Action.WAIT)
    # ... map invalid PAUSE/WAIT combos for queued vs running ...
    return action
```

### 17.8 Execution — cooperative pause in training

`ExecutionEngine` runs blocking PyTorch work in **one thread**; pause sets a `threading.Event`:

```python
# backend/app/infrastructure/execution_engine.py (lines 55–56)

def _execute() -> dict:
    return train_fn(cancel_event=cancel_event, **train_kwargs)
```

Simulated jobs check the flag every batch and save a checkpoint on pause:

```python
# backend/app/infrastructure/jobs/simulated.py (lines 36–52)

while current_epoch < total_epochs:
    for _ in range(batches_per_epoch):
        if cancel_event.is_set():
            paused = True
            break
        time.sleep(batch_sleep_s)
    if paused:
        break
    current_epoch += 1
torch.save(state, checkpoint_path)   # resume later from same epoch
```

### 17.9 How to read the codebase (suggested order)

1. `backend/app/domain/enums.py` — vocabulary.
2. `backend/app/api/main.py` — external interface.
3. `backend/app/application/job_orchestrator.py` — `submit_job`, `tick`, `_dispatch_job`.
4. `backend/app/intelligence/policies/greedy.py` — easiest policy to explain.
5. `backend/app/intelligence/constraints.py` + `ppo_policy.py` — RL + safety.
6. `backend/app/infrastructure/execution_engine.py` + `jobs/simulated.py` — how RUN becomes real work.
7. `frontend/src/App.jsx` — what the user sees.
8. `simulator/train_ppo.py` + `simulator/benchmark.py` — offline research numbers.

### 17.10 Viva one-liners tied to code

| Question | Point to |
|----------|----------|
| “Where is the tick loop?” | `job_orchestrator.py` → `_tick_loop` / `tick` |
| “Where are 550 and 700?” | `defaults.py`; used in `greedy.py` and `App.jsx` |
| “Where is deadline override?” | `constraints.py` + `greedy._deadline_pressure` |
| “Where does PPO load?” | `deps.py` → `_load_ppo()` → `ppo_scheduler.zip` |
| “Why no performance_target force-RUN?” | Removed from `must_force_run`; only in PPO `perf_ratio` reward |
| “Single job at a time?” | `execution_engine.py` `max_workers=1`; orchestrator single-flight check |

---

## 18. Related documents

| File | Use when |
|------|----------|
| [explain.md](explain.md) | Reading & explaining (this file); **§17 = code walkthrough** |
| [DEMO_GUIDE.md](DEMO_GUIDE.md) | Live demo script + 40+ viva Q&A |
| [DOCUMENTATION.md](DOCUMENTATION.md) | Technical architecture details |
| [RUNBOOK.md](RUNBOOK.md) | Copy-paste commands |
| [RESEARCH_PAPER.md](RESEARCH_PAPER.md) | Report / paper draft |
| [README.md](README.md) | Quick project overview |

---

*Last updated to match: India thresholds 550/700, constraint-augmented PPO, 200k training benchmark, dual-policy framework, §17 code walkthrough with file map and snippets.*
