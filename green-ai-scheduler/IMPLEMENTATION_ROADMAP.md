# Implementation Roadmap

> **For the complete click-by-click process, use [RUNBOOK.md](RUNBOOK.md) first.**  
> This file explains each pipeline stage in more technical detail.

Step-by-step guide to evolve from **simulated training** to **real models + CodeCarbon + PPO comparison**.

Your pipeline:

```
Current version (simulated)
      ↓
Add real ResNet50
      ↓
Add real BERT
      ↓
Add CodeCarbon
      ↓
Train/tune PPO
      ↓
Benchmark
      ↓
Compare Greedy vs PPO
```

---

## Step 0 — Current version (simulated) ✅

**What you have:** Scheduler, Greedy/PPO policies, dashboard, tests.

**Training:** `job_type: simulated` runs a fast sleep loop.

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"name":"sim","job_type":"simulated","total_epochs":2,"performance_target":1}'
```

**Use for:** Fast iteration, pytest, scheduler logic demos.

---

## Step 1 — Add real ResNet50 ✅ (implemented)

**Files:**
- `backend/app/infrastructure/jobs/resnet50_cifar.py`
- `backend/app/infrastructure/jobs/registry.py`

**What it does:** `torchvision` ResNet50, 512 CIFAR-10 images, real forward/backward, checkpoint with `model` + `optimizer` + `epoch`.

**Submit:**
```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"name":"resnet-demo","job_type":"resnet50_cifar","total_epochs":1,"performance_target":1}'
```

**First run:** Downloads CIFAR-10 to `./data/cifar10` (from backend cwd). CPU training ~few minutes per epoch.

**Tip:** Use `TICK_INTERVAL_SECONDS=5` for faster scheduling during demos.

---

## Step 2 — Add real BERT ✅ (implemented)

**Files:**
- `backend/app/infrastructure/jobs/bert_imdb.py`

**What it does:** `distilbert-base-uncased` on 200 IMDB rows, real fine-tuning.

**Submit:**
```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"name":"bert-demo","job_type":"bert_imdb","total_epochs":1,"performance_target":1}'
```

**First run:** Downloads model + dataset from Hugging Face (needs network).

---

## Step 3 — Add CodeCarbon ✅ (implemented)

**Files:**
- `backend/app/infrastructure/jobs/carbon_session.py`

**What it does:** Wraps each training **session** (one RUN → pause or COMPLETE) in `EmissionsTracker`. Reports `session_carbon_g` and `session_energy_kwh` to `JobOrchestrator`, which **accumulates** across pause/resume cycles.

**Fallback:** If CodeCarbon fails, uses `power_kw × duration` estimate.

**Verify:** Complete a job and check `carbon_used_g` / `energy_used_kwh` on `GET /jobs/{id}` — values should be non-zero and grow across sessions.

---

## Step 4 — Train / tune PPO

**Goal:** Learned policy that competes with Greedy on the offline simulator.

```bash
cd backend

# Train (50k timesteps default; increase for better results)
PYTHONPATH=.:.. python -m simulator.train_ppo

# Optional: edit simulator/train_ppo.py
#   - timesteps=100000
#   - reward weights for start/complete/wait
```

**Output:** `simulator/models/ppo_scheduler.zip`

**Live use:** Dashboard **PPO** tab or `GET /stats?policy=ppo`

**Known issue:** Early training may learn “never start” — mitigated by force-RUN safety rules in `PPOPolicy` (deadline, performance floor).

---

## Step 5 — Benchmark

**Goal:** Compare Greedy vs PPO on **same** synthetic job arrivals + **real** carbon CSV.

```bash
cd backend
PYTHONPATH=.:.. python -m simulator.benchmark --policies greedy,ppo --horizon 2000
```

**Output:** `simulator/logs/benchmark_results.json`

**Read metrics:**
| Metric | Meaning |
|--------|---------|
| `jobs_completed` | Throughput |
| `carbon_saved_g` | Relative only (simplified accounting) |
| `avg_pause_count` | How often policy pauses |
| `deadline_misses` | Jobs that missed deadline |

**Note:** Benchmark still uses **synthetic jobs**, not real ResNet/BERT — that's intentional for speed.

---

## Step 6 — Compare Greedy vs PPO (live)

### A. Offline (report numbers)
Use benchmark JSON from Step 5.

### B. Live (dashboard)

1. Start backend + frontend
2. **Greedy run:**
   ```bash
   curl "http://localhost:8000/stats?policy=greedy"
   curl -X POST http://localhost:8000/jobs/bulk \
     -H "Content-Type: application/json" \
     -d '{"count":3,"name_prefix":"greedy","job_type":"simulated","total_epochs":2,"performance_target":1}'
   ```
3. Note **Carbon Saved** on dashboard when jobs complete
4. **PPO run:** Repeat with `policy=ppo` and `name_prefix":"ppo"`

### C. Real model comparison (heavier)

```bash
# Greedy + real ResNet
curl "http://localhost:8000/stats?policy=greedy"
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"name":"r-greedy","job_type":"resnet50_cifar","total_epochs":1,"performance_target":1}'

# PPO + real ResNet (after train_ppo)
curl "http://localhost:8000/stats?policy=ppo"
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"name":"r-ppo","job_type":"resnet50_cifar","total_epochs":1,"performance_target":1}'
```

Compare `carbon_used_g`, `pause_count`, `total_duration_hours` per job.

---

## Architecture after this roadmap

```
JobOrchestrator._dispatch_job()
        │
        ▼
jobs/registry.py  ──► get_train_fn(job_type)
        │
        ├── simulated.py      → run_simulated_job
        ├── resnet50_cifar.py → run_resnet50_cifar_job
        └── bert_imdb.py      → run_bert_imdb_job
                │
                ▼
        carbon_session.py (CodeCarbon per session)
                │
                ▼
        ExecutionEngine (thread pool, cancel_event)
                │
                ▼
        JobOrchestrator (accumulate carbon/energy, update DB)
```

---

## Recommended order for your capstone demo

| Day | Task |
|-----|------|
| 1 | Simulated bulk jobs + Greedy dashboard demo |
| 2 | One real ResNet job + show CodeCarbon fields on API |
| 3 | `train_ppo` + benchmark table for report |
| 4 | Live Greedy vs PPO with 3 simulated jobs each |
| 5 | Optional: one BERT job for “real NLP” screenshot |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| CIFAR download fails | Run from `backend/` with network; check `./data/cifar10` |
| HF model download slow | Set `HF_HOME` cache; run once before demo |
| Job stays QUEUED | Lower `TICK_INTERVAL_SECONDS`; check carbon intensity vs thresholds |
| PPO 0 jobs in benchmark | Run `train_ppo` first; check `simulator/models/ppo_scheduler.zip` exists |
| Out of memory | Use `simulated` for demos; ResNet uses CPU and 512 images only |

---

## What to say in the report

> We implemented a carbon-aware scheduler with Greedy (rule-based) and PPO (learned) policies. Training workloads progress from simulated jobs (development) to real ResNet50 and DistilBERT sessions with CodeCarbon telemetry. Offline benchmark compares policies on historical India grid data; live demo compares carbon saved under each policy on the same job queue.

See also [DOCUMENTATION.md](DOCUMENTATION.md) for real vs simulated details.
