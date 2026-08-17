# Complete Runbook — Green Hours Scheduler

End-to-end process: **setup → post jobs → watch dashboard → train PPO → benchmark → compare Greedy vs PPO**.

For architecture and real-vs-simulated details see [DOCUMENTATION.md](DOCUMENTATION.md).  
For what changed recently see [CHANGELOG.md](CHANGELOG.md).

---

## Prerequisites

- Python 3.11+ (3.14 works in this repo)
- Node.js 18+ (frontend)
- Internet for: Electricity Maps API, CIFAR-10 download, Hugging Face models (first real-job run only)
- Carbon dataset at `simulator/data/snapshots_2026-02-10_IN-2025-5_minute.csv` (symlink OK)

---

## Phase 1 — One-time setup

### 1.1 Install backend

```bash
cd green-ai-scheduler/backend
pip install -r requirements.txt
pip install datasets   # required for bert_imdb jobs
```

### 1.2 Configure environment

Create or verify `green-ai-scheduler/.env`:

```env
ELECTRICITY_MAPS_API_KEY=your_key_here
ELECTRICITY_MAPS_ZONE=IN
```

### 1.3 Install frontend

```bash
cd ../frontend
npm install
```

### 1.4 Verify tests (optional)

```bash
cd ../backend
PYTHONPATH=.:.. pytest -q
# Expected: 36 passed
```

---

## Phase 2 — Start the system

Open **two terminals**.

### Terminal 1 — Backend

```bash
cd green-ai-scheduler/backend

# Faster scheduling for demos (optional; default is 60s)
export TICK_INTERVAL_SECONDS=5

PYTHONPATH=. uvicorn app.api.main:app --reload --port 8000
```

Check:
- http://127.0.0.1:8000/ → service info
- http://127.0.0.1:8000/docs → Swagger UI
- http://127.0.0.1:8000/grid/status → real carbon intensity (if API key set)

### Terminal 2 — Frontend

```bash
cd green-ai-scheduler/frontend
npm run dev
```

Open: **http://localhost:5173**

---

## Phase 3 — Post jobs and watch the scheduler

### 3.1 Choose policy first

**Dashboard:** Click **Greedy** or **PPO** tab (top right).

**Or API:**
```bash
curl "http://localhost:8000/stats?policy=greedy"
# or
curl "http://localhost:8000/stats?policy=ppo"
```

> **Note:** PPO needs `simulator/models/ppo_scheduler.zip` (Phase 5). Without it, PPO falls back to Greedy rules.

### 3.2 Submit jobs

#### Option A — Dashboard (easiest)

1. Set number of jobs (e.g. `5`)
2. Click **Submit N jobs**
3. Watch queue update every 10 seconds

#### Option B — Single job (curl)

**Simulated (fast, ~seconds):**
```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "demo-sim",
    "job_type": "simulated",
    "total_epochs": 2,
    "performance_target": 1,
    "priority": 1
  }'
```

**Real ResNet50 (slow, ~minutes, downloads CIFAR-10 first time):**
```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "demo-resnet",
    "job_type": "resnet50_cifar",
    "total_epochs": 1,
    "performance_target": 1,
    "priority": 2
  }'
```

**Real BERT / DistilBERT (slow, downloads HF model first time):**
```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "demo-bert",
    "job_type": "bert_imdb",
    "total_epochs": 1,
    "performance_target": 1,
    "priority": 2
  }'
```

#### Option C — Bulk jobs (curl)

```bash
curl -X POST http://localhost:8000/jobs/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "count": 5,
    "name_prefix": "batch",
    "job_type": "simulated",
    "total_epochs": 2,
    "performance_target": 1,
    "priority": 1
  }'
```

### 3.3 What to watch on the dashboard

| Card / field | Meaning |
|--------------|---------|
| **Carbon Intensity** | Live grid signal (Electricity Maps `IN`) |
| **Waiting** | Jobs in QUEUED / WAITING / PAUSED |
| **Running** | Currently training (max **1**) |
| **Carbon Saved** | Sum of `baseline - actual` for completed jobs |
| **Job status badges** | QUEUED → WAITING → RUNNING → COMPLETED (or PAUSED) |
| **Epoch X / floor Y** | Training progress vs min-epoch before pause allowed |

### 3.4 Job lifecycle (what happens under the hood)

```
POST /jobs  →  QUEUED
     ↓ (scheduler tick + clean grid or deadline pressure)
WAITING or RUNNING
     ↓ (if RUNNING and dirty grid)
PAUSED  →  resume on next clean tick
     ↓ (epochs complete)
COMPLETED  →  carbon/energy accumulated, GaiQ profile updated
```

**Manual pause:**
```bash
curl -X POST http://localhost:8000/jobs/1/pause
curl -X POST http://localhost:8000/jobs/1/resume
```

### 3.5 Inspect job details (API)

```bash
curl http://localhost:8000/jobs          # list all
curl http://localhost:8000/jobs/1      # one job
curl http://localhost:8000/stats       # queue summary
```

Important fields on completed jobs:
- `carbon_used_g` — accumulated CodeCarbon emissions (grams)
- `energy_used_kwh` — accumulated energy
- `baseline_carbon_estimate_g` — GaiQ estimate at submit time
- `pause_count`, `current_epoch`, `total_duration_hours`

---

## Phase 4 — Greedy vs PPO (live comparison)

### 4.1 Run A — Greedy

```bash
curl "http://localhost:8000/stats?policy=greedy"
curl -X POST http://localhost:8000/jobs/bulk \
  -H "Content-Type: application/json" \
  -d '{"count":5,"name_prefix":"greedy-run","job_type":"simulated","total_epochs":2,"performance_target":1}'
```

Wait until all jobs show **COMPLETED** on dashboard. Record **Carbon Saved**.

### 4.2 Run B — PPO

```bash
curl "http://localhost:8000/stats?policy=ppo"
curl -X POST http://localhost:8000/jobs/bulk \
  -H "Content-Type: application/json" \
  -d '{"count":5,"name_prefix":"ppo-run","job_type":"simulated","total_epochs":2,"performance_target":1}'
```

Wait for completion. Compare **Carbon Saved**, pause behavior, and per-job `pause_count`.

### 4.3 Optional — real model under each policy

Repeat Phase 4 with `"job_type": "resnet50_cifar"` and `total_epochs: 1` (much slower).

---

## Phase 5 — Train PPO (offline)

Run from **backend** directory:

```bash
cd green-ai-scheduler/backend
PYTHONPATH=.:.. python -m simulator.train_ppo
```

**Output:**
- `simulator/models/ppo_scheduler.zip` — loaded when you select PPO
- `simulator/logs/training_curves.png` — if matplotlib available

**Tune (optional):** Edit `simulator/train_ppo.py` → increase `timesteps` (e.g. 100000).

**Restart backend** after training so it picks up the new model (or call `/stats?policy=ppo`).

---

## Phase 6 — Offline benchmark

Compares Greedy vs PPO on **historical carbon CSV** + **synthetic job arrivals** (fast, for report tables).

```bash
cd green-ai-scheduler/backend
PYTHONPATH=.:.. python -m simulator.benchmark --policies greedy,ppo --horizon 2000
```

**Output:**
- Printed JSON to terminal
- `simulator/logs/benchmark_results.json`

### Example output (yours will vary)

```json
{
  "greedy": {
    "jobs_completed": 37,
    "carbon_saved_g": 1835.5,
    "avg_pause_count": 0.30,
    "deadline_misses": 1
  },
  "ppo": {
    "jobs_completed": 38,
    "carbon_saved_g": 1900.6,
    "avg_pause_count": 0.05,
    "deadline_misses": 1
  }
}
```

**How to read it:**
- Use for **relative** Greedy vs PPO comparison
- `carbon_saved_g` in benchmark is **not** real kg CO₂ — simplified simulator math
- Live dashboard `carbon_saved_g` uses real job telemetry (still small scale for simulated jobs)

---

## Phase 7 — Full demo script (15 minutes)

| Min | Action |
|-----|--------|
| 0 | Start backend (`TICK_INTERVAL_SECONDS=5`) + frontend |
| 1 | Show `/grid/status` — live India carbon |
| 2 | Greedy tab → submit 5 simulated jobs → show queue moving |
| 3 | Show one job completing — epoch progress, carbon saved |
| 4 | `python -m simulator.benchmark --policies greedy,ppo` — show table |
| 5 | PPO tab → submit 3 jobs → compare pause behavior |
| 6 | (Optional) Submit one `resnet50_cifar` job — real training + CodeCarbon |

---

## Job types quick reference

| `job_type` | Training | Speed | Use case |
|------------|----------|-------|----------|
| `simulated` | Fake sleep loop | Seconds | Demos, tests, bulk jobs |
| `resnet50_cifar` | Real ResNet50 + CIFAR subset | Minutes | “Real CV training” screenshot |
| `bert_imdb` | Real DistilBERT + IMDB subset | Minutes | “Real NLP training” screenshot |

All live jobs use **CodeCarbon** per session (`jobs/carbon_session.py`).

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Jobs stay QUEUED forever | Lower `TICK_INTERVAL_SECONDS`; check intensity vs thresholds (450/550) |
| `GET /` was 404 | Use `/docs` or `/` (now returns links) |
| PPO same as Greedy | Train model first; check `simulator/models/ppo_scheduler.zip` exists |
| PPO benchmark 0 jobs | Fixed in code — re-run benchmark after `train_ppo` |
| `ModuleNotFoundError: datasets` | `pip install datasets` |
| CIFAR download fails | Run backend with network; data goes to `backend/data/cifar10` |
| CodeCarbon geo warnings | Harmless — still records energy/emissions |
| Only one job RUNNING | By design (single worker + CodeCarbon 1:1) |

---

## What is still missing

See [CHANGELOG.md](CHANGELOG.md) § “Still missing” for full list. Summary:

| Item | Status |
|------|--------|
| Cost optimization (PS requirement) | Not implemented — documented descope |
| Benchmark using real ResNet/BERT | Not implemented — benchmark uses synthetic jobs only |
| PPO production-quality tuning | Partial — needs more training timesteps / reward tuning |
| MaskablePPO (strict action masking) | Not implemented |
| GaiQ grade on dashboard UI | Not implemented |
| Regional grid zone (city-level) | Not implemented — `IN` national only |
| Force-kill pause (instant) | Not implemented — cooperative pause only |

---

## File reference

```
green-ai-scheduler/
├── RUNBOOK.md              ← this file
├── CHANGELOG.md            ← what changed + what's missing
├── DOCUMENTATION.md        ← architecture, PS alignment
├── IMPLEMENTATION_ROADMAP.md
├── .env
├── backend/                ← uvicorn from here
├── frontend/               ← npm run dev
└── simulator/
    ├── train_ppo.py
    ├── benchmark.py
    ├── data/*.csv
    └── models/ppo_scheduler.zip
```
