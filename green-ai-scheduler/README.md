# Green Hours Scheduler — Carbon-Aware AI Training

> A capstone final-year project: a full-stack, single-node ML job scheduler that shifts training workloads into low-carbon grid windows, reducing CO₂ emissions without missing deadlines.

---

## What it does

The scheduler watches the electricity grid's **carbon intensity** (gCO₂eq/kWh) in real time and decides **when** to run, pause, or resume PyTorch training jobs. It enforces:

- **Deadline constraints** — jobs must finish before their deadline
- **Minimum-progress floors** — a job won't be paused below a set epoch count
- **Single-node fairness** — at most one job runs at a time (CodeCarbon 1:1 attribution)

Four interchangeable scheduling **policies** compete on the same workload so you can benchmark them side by side:

| Policy | Description |
|--------|-------------|
| **Greedy** | Runs during any window where carbon < threshold; pauses otherwise |
| **Forecast** | Uses a rolling carbon forecast to plan ahead |
| **Constraint Lexicographic** | Deadline-first, then carbon-minimising |
| **PPO** | Reinforcement-learning policy (stable-baselines3) trained on historical Indian grid data |

---

## Dashboard highlights

- **Live carbon intensity card** — colour-coded clean / moderate / dirty
- **GaiQ grade** — A–D letter grade comparing actual vs. baseline carbon per job
- **Expandable job rows** — tap any job to reveal carbon used, energy (kWh), savings vs baseline, epoch progress bar, pause count, and full metadata
- **Status-grouped queue** — jobs are ordered Running → Waiting/Queued → Paused → Completed, newest-first within each group
- **Policy comparison tab** — run a reproducible four-policy benchmark on simulated data without touching live jobs

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy async + SQLite (WAL) |
| ML | PyTorch (CPU / Intel XPU; no hard-coded CUDA) |
| Carbon tracking | CodeCarbon |
| Grid signal | Electricity Maps API (mock fallback if key absent) |
| Policies | Greedy · Forecast · Constraint Lexicographic · PPO (stable-baselines3) |
| Frontend | React 18 + Vite, Vanilla CSS |

---

## Quick start

### 1 — Backend

```bash
cd green-ai-scheduler/backend

# create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# optional: set your Electricity Maps API key
export ELECTRICITY_MAPS_API_KEY=your_key   # omit to use built-in mock
export ELECTRICITY_MAPS_ZONE=IN            # India national grid (default)

uvicorn app.api.main:app --reload --port 8000
```

### 2 — Frontend

```bash
cd green-ai-scheduler/frontend
npm install
npm run dev
```

Open **http://localhost:5173** — the dashboard polls `/stats` and `/jobs` every 10 seconds.

---

## Running tests

```bash
cd green-ai-scheduler/backend
PYTHONPATH=. pytest -v
```

Policy-parametric tests run against both Greedy and PPO fixtures automatically.

---

## PPO training & four-policy benchmark

Place `snapshots_2026-02-10_IN-2025-5_minute.csv` inside `simulator/data/` for real Indian grid carbon data (synthetic fallback is used if the file is missing).

```bash
cd green-ai-scheduler/backend

# train the PPO agent
PYTHONPATH=.:.. python -m simulator.train_ppo

# benchmark all four policies on the same workload
PYTHONPATH=.:.. python -m simulator.benchmark --policies greedy,ppo
```

---

## Architecture overview

```
Frontend (React/Vite)
    │  REST + polling
    ▼
FastAPI  ──▶  JobOrchestrator
                 ├── DecisionEngine   (Greedy / Forecast / Lex / PPO)
                 ├── CarbonEstimator  (Electricity Maps / mock)
                 ├── GaiQEngine       (A–D grade calculator)
                 ├── PersistentJobStore (SQLite WAL)
                 └── ExecutionEngine  (ThreadPoolExecutor, CodeCarbon)
```

**Key design rule:** the intelligence layer (DecisionEngine) never writes to the database. Only `JobOrchestrator` writes; `ExecutionEngine` reports session results back up.

---

## Job status machine

```
POST /jobs  →  QUEUED
  Tick + WAIT on candidate  →  WAITING
  Tick + RUN                →  RUNNING  (worker slot confirmed)
  WAIT / PAUSE on running   →  PAUSED   (system-managed; auto-resumable)
  POST /jobs/{id}/pause     →  MANUALLY_PAUSED  (never auto-resumed)
  POST /jobs/{id}/resume    →  QUEUED
  Completion                →  COMPLETED
```

---

## Supported job types

| Type | Model | Dataset |
|------|-------|---------|
| `simulated` | Synthetic fast loop | — |
| `resnet50_cifar` | ResNet-50 | CIFAR-10 subset |
| `bert_imdb` | DistilBERT / GPT-2-small | IMDB subset |

Default power profiles (refined after first completed run of each type):

| Type | Power | Duration |
|------|-------|----------|
| `resnet50_cifar` | 0.15 kW | 0.25 h |
| `bert_imdb` | 0.12 kW | 0.20 h |
| `simulated` | 0.05 kW | 0.05 h |

---

## Scope decisions

- **Cost optimization is descoped** for this milestone. Carbon emissions, deadlines, and training-progress floors are the operative constraints.
- **Carbon intensity** (gCO₂eq/kWh) is the greenness signal — more actionable than renewable percentage, and matches both Electricity Maps and the PPO training dataset.
- **Single-machine scheduling** — `ThreadPoolExecutor(max_workers=1)` ensures CodeCarbon can attribute energy to one job at a time.
- **Performance target is a soft constraint** — enforced via PPO reward penalties and benchmark violation metrics, not as a hard override (except near-deadline force-run).

---

## Known limitations

- Cooperative pause only — the thread checks a cancel token at batch boundaries; no force-kill
- PPO invalid actions are treated as no-ops (no MaskablePPO from sb3-contrib)
- Grid zone is India national (`IN`), not city-specific
- `energy_used_kwh` and `carbon_used_g` are tracked separately for accurate power-profile derivation

---

## Further reading

| Document | Purpose |
|----------|---------|
| [DOCUMENTATION.md](DOCUMENTATION.md) | Full architecture, real vs. simulated data, Greedy vs. PPO details, known issues |
| [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) | Upgrade path: simulated → ResNet → BERT → CodeCarbon → PPO → benchmark |
| [RUNBOOK.md](RUNBOOK.md) | Step-by-step start-up and operating guide |
| [DEMO_GUIDE.md](DEMO_GUIDE.md) | External demo script + 15–20 min panel viva guide |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [RESEARCH_PAPER.md](RESEARCH_PAPER.md) | Academic write-up of the approach |
