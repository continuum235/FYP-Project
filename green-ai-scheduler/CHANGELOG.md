# Changelog & Project Status

What was built, what changed recently, and what is still missing vs the problem statement.

---

## Recent changes (implementation pipeline)

### Job training layer (new)

| File | Change |
|------|--------|
| `backend/app/infrastructure/jobs/registry.py` | Routes `job_type` → correct training function |
| `backend/app/infrastructure/jobs/simulated.py` | Simulated training (moved from `execution_engine.py`) |
| `backend/app/infrastructure/jobs/resnet50_cifar.py` | **Real** ResNet50 on 512 CIFAR-10 images |
| `backend/app/infrastructure/jobs/bert_imdb.py` | **Real** DistilBERT on 200 IMDB rows |
| `backend/app/infrastructure/jobs/carbon_session.py` | **CodeCarbon** `EmissionsTracker` per training session |
| `backend/app/application/job_orchestrator.py` | Uses `get_train_fn()` instead of hard-coded simulated |
| `backend/requirements.txt` | Added `datasets` for Hugging Face |

### API & frontend

| File | Change |
|------|--------|
| `backend/app/api/main.py` | `GET /` root route; `POST /jobs/bulk` for batch submit |
| `frontend/src/App.jsx` | Submit N jobs button; Greedy/PPO policy tabs |
| `backend/app/config.py` | Loads `.env` from project root; `ELECTRICITY_MAPS_API_KEY` |

### PPO & benchmark fixes

| File | Change |
|------|--------|
| `backend/app/intelligence/policies/ppo_policy.py` | Observation clipping; force-RUN safety rules; Greedy fallback if no model |
| `simulator/train_ppo.py` | Fixed env observation bounds; improved rewards; 50k timesteps default |
| `simulator/benchmark.py` | Fixed deadline double-counting; arrival filter for jobs |

### Documentation

| File | Purpose |
|------|---------|
| `DOCUMENTATION.md` | Architecture, real vs simulated, PS table, issues |
| `IMPLEMENTATION_ROADMAP.md` | Pipeline steps simulated → ResNet → BERT → PPO |
| `RUNBOOK.md` | **Full end-to-end run process** |
| `REPORT.md` | Capstone report bullet points |
| `CHANGELOG.md` | This file |

### Dataset & config

| Item | Change |
|------|--------|
| `simulator/data/snapshots_….csv` | Symlink to user CSV at repo root |
| `.env` | `ELECTRICITY_MAPS_API_KEY` + `ELECTRICITY_MAPS_ZONE=IN` |

---

## What works today

| Feature | Live system | Offline benchmark |
|---------|-------------|-------------------|
| Greedy scheduling | ✅ | ✅ |
| PPO scheduling | ✅ (with trained model) | ✅ |
| Simulated jobs | ✅ | ✅ (synthetic) |
| Real ResNet50 jobs | ✅ | ❌ |
| Real BERT jobs | ✅ | ❌ |
| CodeCarbon telemetry | ✅ live sessions | ❌ formula only |
| Electricity Maps API | ✅ | ✅ (CSV) |
| Dashboard | ✅ | N/A |
| Checkpoint pause/resume | ✅ | N/A |
| 36 pytest tests | ✅ | N/A |

---

## Still missing (honest list)

### Problem statement gaps

| PS requirement | Status | Notes |
|----------------|--------|-------|
| Cost constraints | **Not done** | Documented intentional descope in README/REPORT |
| High renewable % signal | **Substituted** | Uses carbon intensity (gCO₂/kWh) — documented |

### Technical gaps

| Item | Priority | Notes |
|------|----------|-------|
| Benchmark with real ResNet/BERT | Low | Too slow; benchmark intentionally uses synthetic jobs |
| PPO reward tuning / longer training | Medium | Works but not production-tuned; try 100k+ timesteps |
| `MaskablePPO` (sb3-contrib) | Low | Invalid actions handled via mapping + force-RUN |
| GaiQ A–D grade on dashboard | Low | Computable from API fields, not shown in UI |
| CodeCarbon region from grid zone | Low | May default geo to Canada if IP lookup fails — emissions still recorded |
| Real cost tracking (`cost_used`) | N/A | Out of scope |
| Multi-node / Kubernetes | N/A | Out of scope |
| Instant force-kill pause | N/A | Cooperative pause only — documented |

### Nice-to-have

- Submit job form with `job_type` selector on dashboard (today: simulated only in UI bulk button)
- Delete / reset jobs API
- Postgres option for multi-user
- Training curves in dashboard from PPO logs

---

## Version history (milestone summary)

### v0 — Initial capstone build
- Full layer architecture (API → Orchestrator → Intelligence + Infrastructure)
- Greedy policy, simulated jobs only
- SQLite, dashboard, 36 tests

### v1 — PPO + benchmark + docs
- PPO training/simulator, benchmark script
- DOCUMENTATION.md, PS alignment table
- `.env` + CSV fixes

### v2 — Real training + CodeCarbon (current)
- ResNet50, BERT job implementations
- CodeCarbon per session
- Job registry, bulk submit, RUNBOOK

---

## Next recommended work (if continuing)

1. Dashboard: job type dropdown (`simulated` / `resnet50_cifar` / `bert_imdb`)
2. PPO: train 100k timesteps, log reward curve for report
3. One recorded demo: Greedy bulk → benchmark JSON → PPO bulk → compare carbon saved
4. Report: paste benchmark table + screenshot of live dashboard with real ResNet job
