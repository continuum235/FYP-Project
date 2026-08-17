# Green Hours Scheduling for Sustainable AI Training

Carbon-aware ML job scheduler for a single-node capstone project. The system decides **when** to run, pause, or resume training jobs based on grid carbon intensity (gCO₂eq/kWh), while enforcing deadline and minimum-training-progress constraints.

**Full technical documentation:** [DOCUMENTATION.md](DOCUMENTATION.md) — architecture, real vs simulated data, Greedy vs PPO, known issues.

**Step-by-step upgrade path:** [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) — simulated → ResNet → BERT → CodeCarbon → PPO → benchmark.

**Full run process (start here):** [RUNBOOK.md](RUNBOOK.md)

**External demo & viva presentation:** [DEMO_GUIDE.md](DEMO_GUIDE.md) — detailed explanation + 15–20 min panel script

## Scope decisions

- **Cost optimization is descoped** for this milestone. The faculty problem statement names cost constraints; this build intentionally focuses on carbon emissions, deadlines, and training performance (min-epoch floor). Cost tracking may be added later.
- **Carbon intensity** is used instead of renewable-percentage as the operative greenness signal (more actionable; matches Electricity Maps and the PPO training dataset).
- **Single-machine scheduling** — at most one job `RUNNING` at a time (`ThreadPoolExecutor(max_workers=1)` for CodeCarbon 1:1 attribution).

## Tech stack

- Backend: Python 3.11, FastAPI, SQLAlchemy async + SQLite (WAL)
- ML: PyTorch (CPU / XPU; no hard-coded CUDA)
- Policies: Greedy (primary) + PPO (stable-baselines3)
- Frontend: React + Vite

## Setup

### Backend

```bash
cd green-ai-scheduler/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ELECTRICITY_MAPS_API_KEY=your_key   # optional; mock used if unset
export ELECTRICITY_MAPS_ZONE=IN            # India national grid
uvicorn app.api.main:app --reload --port 8000
```

### Frontend

```bash
cd green-ai-scheduler/frontend
npm install
npm run dev
```

Open http://localhost:5173 — polls `/stats` and `/jobs` every 10s. Switch Greedy/PPO via dashboard tabs.

### Tests

```bash
cd green-ai-scheduler/backend
PYTHONPATH=. pytest -v
```

Policy-parametric tests run against both Greedy and PPO fixtures.

### PPO training & benchmark

```bash
cd green-ai-scheduler/backend
PYTHONPATH=.:.. python -m simulator.train_ppo
PYTHONPATH=.:.. python -m simulator.benchmark --policies greedy,ppo
```

Place `snapshots_2026-02-10_IN-2025-5_minute.csv` in `simulator/data/` for real carbon data (synthetic fallback if missing).

## Architecture

```
API → JobOrchestrator → DecisionEngine / CarbonEstimator / GaiQEngine
                      → PersistentJobStore / ExecutionEngine
```

Intelligence never writes to the database. `ExecutionEngine` reports sessions; `JobOrchestrator` is the sole writer.

### Status machine

- `POST /jobs` → `QUEUED`
- Tick + `WAIT` on start-candidate → `WAITING`
- Tick + `RUN` → `RUNNING` (once worker slot confirms)
- `WAIT`/`PAUSE` on running job → `PAUSED` (system)
- `POST /jobs/{id}/pause` → `MANUALLY_PAUSED` (never auto-resumed)
- `POST /jobs/{id}/resume` → `QUEUED`

### Performance constraint

`performance_target` is a **soft** training-progress goal. It is enforced via PPO reward penalties and benchmark `performance_violations` metrics — not as a hard scheduler override. **Hard force-RUN** applies only when the deadline is critical, Greedy deadline pressure is high, or `pause_count` reaches the limit.

## Known limitations

- Cooperative pause only (thread checks cancel token at batch level; no force-kill)
- PPO invalid actions treated as no-op without sb3-contrib MaskablePPO
- India national grid zone (not city-specific)
- `energy_used_kwh` and `carbon_used_g` tracked separately for valid profile power derivation

## Job types

| Type | Description |
|------|-------------|
| `resnet50_cifar` | ResNet50 on CIFAR-10 subset |
| `bert_imdb` | BERT/GPT2-small on IMDB subset |
| `simulated` | Fast simulated job for tests |

Seed profile defaults (refined after first completed run per type):

- ResNet50: 0.15 kW, 0.25 h
- BERT: 0.12 kW, 0.20 h
- Simulated: 0.05 kW, 0.05 h

## Report notes

Document cost descope, carbon-intensity vs renewable substitution, and single-node constraint in the final capstone report.
