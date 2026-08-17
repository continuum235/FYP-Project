# Green Hours Scheduler — Project Explanation & External Demo Guide

Use this document to **understand the full project** and to **present it live** in front of faculty, externals, or a viva panel.

**Related docs:**
- [RUNBOOK.md](RUNBOOK.md) — technical commands
- [DOCUMENTATION.md](DOCUMENTATION.md) — architecture & real vs simulated
- [REPORT.md](REPORT.md) — short report bullets

---

## Is this a good final year project?

**Yes — this is a solid, defensible final year (capstone) project**, provided you present it honestly and lead with what works best live (Greedy + simulated jobs + live grid API).

### Why externals will view it positively

| Strength | Why it matters |
|----------|----------------|
| **Clear real-world problem** | AI carbon footprint / green grid scheduling is timely and relevant |
| **End-to-end system** | Not just a paper or script — backend, DB, API, UI, tests, docs |
| **Live integration** | Real Electricity Maps API for India — demonstrable on stage |
| **Two scheduling approaches** | Greedy (explainable) + PPO (research depth) |
| **Constraints** | Deadline + training progress — shows depth beyond "pause when dirty" |
| **Layered architecture** | API → Application → Intelligence → Infrastructure |
| **Measurable outcomes** | Carbon saved, pause count, benchmark comparison |
| **Documentation & tests** | 36 pytest tests, full MD documentation set |

### What externals may challenge (answers in Part 8)

| Weakness | How to handle |
|----------|----------------|
| Cost constraint not implemented | Documented descope; future work |
| PPO doesn't beat Greedy | Valid research comparison — be honest |
| Simulated jobs for main demo | Fast demo; real ResNet/BERT available |
| Single machine only | By design; cluster = future work |
| Benchmark not "real kg CO₂" | Policy comparison only |
| Jobs ran at 605 gCO₂/kWh | Old behavior forced RUN via `performance_target`; now carbon-aware WAIT/PAUSE unless deadline is critical |

### Grade expectation (honest)

| If you… | Likely impression |
|---------|-------------------|
| Live demo works + clear explanation + honest scope | **Good to very good** project |
| Only slides, no working demo | Weaker |
| Overclaim PPO results | Red flag — stay precise |
| Show tests + architecture + benchmark | Stronger credibility |

**Bottom line:** For B.Tech / final year CS or IT on **sustainable AI / systems / ML**, this is **good and above average** with a live demo.

---

## Part 1 — What is this project?

### Problem (faculty problem statement)

Training large AI models uses a lot of electricity. That electricity is **dirtier at some times of day** (coal-heavy nights) and **cleaner at others** (more solar midday). Most training runs **ignore the grid** and train continuously.

**Our solution:** A **carbon-aware job scheduler** that decides **when** to run, pause, or resume ML training based on **live grid carbon intensity** — while still respecting **deadlines** and **minimum training progress**.

### What we built

A **single-machine scheduler** (not cloud/Kubernetes) with:

| Component | Role |
|-----------|------|
| **FastAPI backend** | REST API for jobs, grid status, stats |
| **JobOrchestrator** | Brain — ticks every N seconds, picks one job, asks policy, dispatches work |
| **GreedyPolicy** | Rule-based: run when carbon &lt; 450, pause when &gt; 550 gCO₂/kWh |
| **PPOPolicy** | ML-learned alternative (trained offline on 2025 India carbon data) |
| **ExecutionEngine** | Runs one training job at a time in a worker thread |
| **CarbonEstimator** | Live carbon from **Electricity Maps API** (zone `IN`) |
| **GaiQEngine** | Compares scheduled vs unscheduled carbon estimate (grade A–D) |
| **SQLite database** | Persistent job state, checkpoints, carbon totals |
| **React dashboard** | Live view: grid carbon, queue, carbon saved, policy toggle |

### One-line elevator pitch

> *"We built a scheduler that pauses AI training when the electricity grid is dirty and resumes when it's clean — like choosing green hours to run your washing machine, but for machine learning."*

### What we deliberately did NOT build

- **Cost optimization** — PS mentions it; we document it as **out of scope** for this milestone
- **Multi-server placement** — single node only; one job runs at a time
- **Kubernetes** — not part of this capstone

---

## Part 2 — How it works (simple flow)

```
You submit a job (POST /jobs)
        ↓
Job stored as QUEUED in SQLite
        ↓
Every 60s (or 10s for demo): JobOrchestrator wakes up
        ↓
Reads live carbon intensity from Electricity Maps
        ↓
Asks Greedy (or PPO): "Run, wait, or pause?"
        ↓
If RUN → ExecutionEngine starts training (simulated / ResNet / BERT)
        ↓
CodeCarbon measures emissions for that session
        ↓
On pause → checkpoint saved; on complete → job COMPLETED
        ↓
Dashboard shows carbon saved vs baseline estimate
```

### Job statuses (what externals will see on screen)

| Status | Meaning |
|--------|---------|
| `QUEUED` | Just submitted |
| `WAITING` | Scheduler waiting for cleaner grid |
| `RUNNING` | Training in progress (only **one** at a time) |
| `PAUSED` | System paused (high carbon) — will auto-resume |
| `MANUALLY_PAUSED` | User paused — won't resume until you click Resume |
| `COMPLETED` | All epochs done |
| `FAILED` | Error or deadline missed |

### Constraints enforced

1. **Deadline** — if time is running out, job runs even if carbon is high (hard override)  
2. **Performance goal** — `performance_target` is a soft training goal (PPO reward penalty), not a hard force-RUN  
3. **Carbon** — prefer running when intensity is low (Greedy thresholds or PPO learned decision)

---

## Part 3 — Architecture (for technical questions)

```
┌──────────────┐     HTTP      ┌─────────────────┐
│   React UI   │ ────────────► │   FastAPI API   │
└──────────────┘               └────────┬────────┘
                                        │
                               ┌────────▼────────┐
                               │ JobOrchestrator │
                               └───┬─────────┬───┘
                    ┌─────────────┘         └─────────────┐
                    ▼                                     ▼
           ┌────────────────┐                  ┌─────────────────┐
           │  Intelligence   │                  │ Infrastructure  │
           │ CarbonEstimator │                  │ SQLite JobStore │
           │ GaiQEngine      │                  │ ExecutionEngine │
           │ Greedy / PPO    │                  └─────────────────┘
           └────────────────┘
```

**Key design rule:** API only talks to `JobOrchestrator`. Intelligence never writes to the database directly. Training code reports sessions back; orchestrator updates carbon and status.

---

## Part 4 — Real vs simulated (be honest with panel)

| What | Real? | Notes |
|------|-------|-------|
| Grid carbon on dashboard | **Yes** | Electricity Maps API, India `IN` |
| Scheduler logic | **Yes** | Pause/resume, deadlines, policies |
| `simulated` jobs | Fast fake loop | Best for **live demo** (seconds) |
| `resnet50_cifar` jobs | **Real PyTorch** | CIFAR subset, ~1 min+ per epoch |
| `bert_imdb` jobs | **Real DistilBERT** | IMDB subset, ~1 min+ per epoch |
| CodeCarbon on live jobs | **Yes** | Per training session |
| Offline benchmark JSON | Synthetic jobs | For **report table** only |

**Say this:** *"The scheduler and grid feed are real; we use fast simulated jobs for the live demo and real ResNet/BERT when we want to show actual training."*

---

## Part 5 — Greedy vs PPO (what to tell externals)

| | Greedy | PPO |
|---|--------|-----|
| Type | Hand-written rules | Reinforcement learning |
| Demo | **Use this** | Show as comparison |
| Reliability | High, explainable | Trained, can miss deadlines in benchmark |
| When carbon low | Run | Run |
| When carbon high | Pause/wait | Learned behavior |

**Benchmark result (your run):** Greedy completed more jobs with fewer deadline misses. PPO is included to show we explored learned scheduling — not that it always wins.

---

## Part 6 — External demo script (15–20 minutes)

### Before the panel arrives (30 min earlier)

```bash
# Terminal 1 — Backend (from backend folder)
cd green-ai-scheduler/backend
pip install -r requirements.txt datasets   # if not done
export TICK_INTERVAL_SECONDS=5            # faster scheduling for demo
PYTHONPATH=. uvicorn app.api.main:app --reload --port 8000

# Terminal 2 — Frontend
cd green-ai-scheduler/frontend
npm install   # if not done
npm run dev
```

**Pre-flight checklist:**

- [ ] http://localhost:5173 loads dashboard  
- [ ] http://localhost:8000/grid/status shows `"source": "electricity_maps"`  
- [ ] `.env` has `ELECTRICITY_MAPS_API_KEY` (do not show key on screen)  
- [ ] Close unrelated tabs; zoom browser to 125% if projecting  
- [ ] Optional: run benchmark once so you have JSON numbers ready  

```bash
# Optional — have benchmark numbers ready on paper
cd green-ai-scheduler/backend
PYTHONPATH=.:.. python -m simulator.benchmark --policies greedy,ppo
```

---

### Minute 0–2: Introduction

**Say:**
> "Green Hours Scheduling reduces the carbon footprint of AI training by scheduling work during cleaner grid periods. We use live carbon intensity from Electricity Maps for India, enforce deadlines and minimum training progress, and compare a rule-based Greedy policy with a PPO reinforcement-learning policy."

**Show:** Title slide or dashboard homepage (empty queue is fine).

---

### Minute 2–4: Live grid carbon

**Do:** Point at the **Carbon Intensity** card on the dashboard.

**Say:**
> "This is live data — grams of CO₂ per kilowatt-hour for the India national grid. Red border means dirty; green means clean. The scheduler uses this signal every tick to decide whether to run or wait."

**Backup if API fails:** Card may show `mock` source — say *"We have a fallback mock mode for offline testing; in production we use Electricity Maps."*

**Optional API proof (if asked):**
```bash
curl -s http://localhost:8000/grid/status | python3 -m json.tool
```

---

### Minute 4–8: Submit jobs under Greedy

**Do:**
1. Click **Greedy** tab (top right)  
2. Set job count to **5**  
3. Click **Submit 5 jobs**  
4. Wait and narrate status changes  

**Say while jobs move:**
> "Jobs enter QUEUED. The orchestrator evaluates the highest-priority job each tick. If carbon is below our run threshold, it goes RUNNING. If carbon rises, it PAUSES and saves a checkpoint — we don't lose epoch progress. Carbon used accumulates via CodeCarbon each session."

**Point at:**
- **Waiting / Running** counts  
- **Carbon Saved** increasing as jobs complete  
- Epoch line: `Epoch 2 / floor 1 (target 2)`  

---

### Minute 8–10: Manual pause (optional but impressive)

**Do:** If a job is `RUNNING`, click **Pause** on that row.

**Say:**
> "Manual pause sets MANUALLY_PAUSED — the scheduler will never auto-resume this job, even if the grid becomes clean. That respects explicit user control."

**Do:** Click **Resume**, show it re-enters the queue.

---

### Minute 10–12: Show API / architecture (if technical panel)

**Do:** Open http://localhost:8000/docs in another tab.

**Say:**
> "All routes go through JobOrchestrator — the API never bypasses the application layer. We have bulk submit, per-job pause/resume, grid status, and stats with policy switching."

**Quick curl (optional):**
```bash
curl -s http://localhost:8000/jobs | python3 -m json.tool | head -40
curl -s http://localhost:8000/stats?policy=greedy | python3 -m json.tool
```

---

### Minute 12–14: PPO comparison

**Do:** Click **PPO** tab → submit **3 jobs**.

**Say:**
> "We trained a PPO agent offline on a full year of historical India carbon data. Live, it uses the same orchestrator and constraints. In our offline benchmark, Greedy completed more jobs; PPO is our learned alternative for research comparison."

**Show benchmark JSON or a slide with your numbers:**

| Metric | Greedy | PPO |
|--------|--------|-----|
| jobs_completed | 37 | 29 |
| deadline_misses | 1 | 9 |
| avg_pause_count | 0.30 | 0.62 |

---

### Minute 14–16: Real training (optional — only if time)

**Say:**
> "For simulated jobs we use a fast loop for demos. We also support real ResNet50 on CIFAR-10 and DistilBERT on IMDB with CodeCarbon telemetry."

**Only run if you pre-tested and have time** (downloads already cached):
```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"name":"resnet-demo","job_type":"resnet50_cifar","total_epochs":1,"performance_target":1}'
```

**Warn panel:** *"First ResNet run downloads CIFAR once (~170 MB); subsequent runs are fast."*

---

### Minute 16–18: Scope & limitations (important for honesty)

**Say:**
> "Three scope notes for evaluators: First, we use carbon intensity rather than renewable percentage — they're correlated but not identical, and intensity is what Electricity Maps provides. Second, cost optimization from the problem statement is documented as out of scope for this milestone. Third, this is single-machine scheduling — one training job at a time by design, for accurate CodeCarbon attribution."

---

### Minute 18–20: Q&A preparation

See **Part 8 — External viva Q&A** below (30+ questions with answers).

---

## Part 7 — Demo modes (choose one)

### Mode A — Safe demo (recommended for externals)

| Setting | Value |
|---------|-------|
| Policy | **Greedy** |
| Job type | **simulated** (dashboard bulk button) |
| Tick interval | `TICK_INTERVAL_SECONDS=10` |
| Duration | Jobs complete in ~1–3 minutes total |

### Mode B — Research demo (includes PPO + benchmark)

Everything in Mode A, plus:
```bash
PYTHONPATH=.:.. python -m simulator.benchmark --policies greedy,ppo
```
Show printed JSON or `simulator/logs/benchmark_results.json`.

### Mode C — Full ML demo (only if pre-tested)

Mode A + one `resnet50_cifar` job with CIFAR already downloaded.

**Do NOT** submit ResNet/BERT for the first time in front of panel without caching — downloads take 5–15 minutes.

---

## Part 8 — External viva Q&A (questions with answers)

Study these before your presentation. Answers are written in **spoken style** — adapt to your own words.

---

### A. General & motivation

**Q1: What is your project about in one sentence?**  
**A:** We built a scheduler that decides when to run, pause, or resume ML training based on how clean the electricity grid is right now — to reduce training carbon footprint without missing deadlines or stalling training progress.

**Q2: Why is this problem important?**  
**A:** AI training consumes large amounts of electricity. If training runs during coal-heavy hours, emissions are much higher than during solar-heavy hours for the same accuracy. Most training today ignores the grid and runs 24/7. We shift work to greener time windows.

**Q3: What is novel about your work?**  
**A:** We combine live grid carbon data, active pause/resume scheduling with checkpointing, constraint handling — deadlines and minimum epochs — and compare rule-based Greedy scheduling with a PPO reinforcement-learning policy on real historical grid data.

**Q4: Who would use this system?**  
**A:** Research labs, universities, or companies running long training jobs on a single server or workstation who want to reduce carbon without rewriting their models — they submit jobs to our scheduler instead of running training directly.

**Q5: Is this a final year project level work?**  
**A:** Yes. We delivered a full stack — API, database, orchestrator, two policies, dashboard, 36 automated tests, offline benchmark, and integration with Electricity Maps and CodeCarbon. Scope limitations like cost optimization are documented explicitly.

---

### B. Problem statement alignment

**Q6: Does your project satisfy the problem statement?**  
**A:** Mostly yes. We reduce carbon through intelligent scheduling during cleaner grid periods, and enforce deadline and training-performance constraints. Cost optimization from the PS is intentionally descoped and documented — we focused this milestone on carbon, deadlines, and progress.

**Q7: You use carbon intensity, not renewable percentage. Is that wrong?**  
**A:** The PS mentions renewable availability; we use carbon intensity in gCO₂ per kWh because it is the standard actionable signal from Electricity Maps, it matches our PPO dataset, and it directly measures emissions impact. They are correlated but not identical — we document this substitution in our report.

**Q8: Why didn't you implement cost constraints?**  
**A:** Time and scope. Cost needs electricity pricing data and billing logic separate from carbon. We prioritized carbon scheduling as the core thesis and documented cost as future work so it is a scope decision, not an oversight.

**Q9: What constraints does your system enforce?**  
**A:** Three layers: (1) **Hard deadline** — force RUN when deadline is critical or Greedy deadline pressure is high; (2) **Soft performance** — `performance_target` is encouraged via PPO reward penalties, not a hard override; (3) **Carbon** — Greedy uses fixed thresholds; PPO learns deferral from context (forecast, slack, queue).

**Q10: How do you define "training performance"?**  
**A:** As a soft goal via `performance_target`. The scheduler may pause before that epoch if carbon is high and deadline slack allows — matching paper-style batch deferral. Violations are tracked in benchmark metrics and penalized in PPO training reward.

---

### C. Architecture & design

**Q11: Explain your system architecture.**  
**A:** Four layers. The **API** (FastAPI) only talks to **JobOrchestrator** (application layer). The orchestrator calls **Intelligence** — CarbonEstimator, GaiQEngine, Greedy/PPO — for decisions, and **Infrastructure** — SQLite store and ExecutionEngine — for persistence and training. Intelligence never writes to the database directly; the orchestrator is the sole writer.

**Q12: Why can't the API call the database directly?**  
**A:** To keep layers decoupled. All business rules — status transitions, carbon accumulation, profile updates — live in JobOrchestrator. That prevents bugs like double-counting carbon or policies bypassing constraints.

**Q13: What is the difference between QUEUED, WAITING, and PAUSED?**  
**A:** **QUEUED** — just submitted. **WAITING** — scheduler decided to wait for cleaner grid. **PAUSED** — was running and system paused it (high carbon); can auto-resume. **MANUALLY_PAUSED** — user paused; only explicit resume clears it.

**Q14: Why only one job RUNNING at a time?**  
**A:** Two reasons: our ExecutionEngine uses one worker thread for CPU training, and CodeCarbon measures host-level power — with one active job, emissions attribution is accurate. This matches our single-machine capstone scope.

**Q15: What is GaiQ?**  
**A:** Green AI Quality — we compare baseline carbon — estimated if the job ran immediately unscheduled — versus actual measured carbon after scheduling. Ratio maps to grades A through D. Baseline is computed once at submit time; actual accumulates across training sessions.

**Q16: What database did you use and why?**  
**A:** SQLite with WAL mode and busy timeout. It is persistent, needs no separate server, suits a single-node capstone, and handles concurrent API reads plus orchestrator writes safely.

---

### D. Technical implementation

**Q17: What technologies did you use?**  
**A:** Python 3, FastAPI, SQLAlchemy async, PyTorch, Hugging Face transformers, CodeCarbon, stable-baselines3 for PPO, React and Vite for the dashboard, Electricity Maps API for live carbon, and pytest for 36 automated tests.

**Q18: How does pause and resume work without losing training progress?**  
**A:** Cooperative cancellation. We pass a threading Event into the training loop; it checks every batch. On pause, we save model, optimizer, and epoch to a checkpoint file. On resume, we load the checkpoint and continue from that epoch. Carbon from each session is added, not overwritten.

**Q19: What is CodeCarbon's role?**  
**A:** It measures real energy use and emissions per training session on the host. JobOrchestrator accumulates `carbon_used_g` and `energy_used_kwh` across pause and resume cycles. We use it for live ResNet, BERT, and simulated jobs.

**Q20: Are your training jobs real or fake?**  
**A:** Both. **Simulated** jobs use a fast loop for demos and tests. **ResNet50** trains on a CIFAR-10 subset with real PyTorch. **BERT** fine-tunes DistilBERT on an IMDB subset. All go through the same scheduler and CodeCarbon wrapper.

**Q21: How often does the scheduler make decisions?**  
**A:** Every tick — default 60 seconds, we use 10 seconds for demos. Each tick it evaluates at most one job and calls the policy once — that is our single-flight evaluation scope.

**Q22: What tests did you write?**  
**A:** 36 pytest tests covering the database, execution engine, Greedy and PPO policies, orchestrator integration — lifecycle, pause and resume, manual pause, single-flight, SQLite concurrency — and API endpoints. Policy tests run parametrically for both Greedy and PPO.

---

### E. Greedy vs PPO

**Q23: Explain Greedy policy.**  
**A:** Rule-based baseline: run when carbon &lt; 450 gCO₂/kWh; pause when &gt; 550 while running (hysteresis band in between). Force RUN only when deadline pressure is high, pause limit is reached, or deadline is in the critical window.

**Q24: Explain PPO policy.**  
**A:** PPO trained offline on India carbon data. It outputs RUN/WAIT/PAUSE from a 12-dimensional state (carbon, forecast, clean-window ETA, deadline slack, queue length, progress). Unlike Greedy, it does not use fixed thresholds — it learns context-dependent deferral. Hard overrides apply only for critical deadline and max pauses.

**Q25: Why didn't PPO beat Greedy in your benchmark?**  
**A:** Greedy is hand-tuned for exactly this threshold problem. Our PPO had limited training — about 50k steps — on a simplified simulator. It paused more often, completed fewer jobs, and missed more deadlines. That is a valid research result — learned policies need more tuning to beat strong baselines.

**Q26: Then why include PPO at all?**  
**A:** To show we explored learned scheduling, not only rules. For a capstone, comparing two policies on identical data demonstrates research methodology. Greedy is our production recommendation; PPO is the ML extension.

**Q27: What data did you use to train PPO?**  
**A:** Electricity Maps historical export for India 2025 — about 105,000 rows at 5-minute resolution. We split chronologically — first 10 months train, last 2 months validation — so we test generalization to unseen time periods.

---

### F. Carbon, grid & environment

**Q28: Is the carbon on your dashboard real?**  
**A:** Yes, when our API key is set. We call Electricity Maps for zone IN — India national grid. The response shows source `electricity_maps`. Without a key, it falls back to mock 500 gCO₂/kWh for offline dev.

**Q29: How much carbon did your project actually save?**  
**A:** On live jobs, carbon saved is the sum over completed jobs of baseline estimate minus measured carbon. For our ResNet demo job, roughly 21 grams saved versus baseline on that single job. Benchmark totals like 1800g are simulator-relative comparisons, not absolute real-world savings claims.

**Q30: Why India grid only?**  
**A:** Our dataset and API zone are India national average — Mainland India. It matches our capstone data source. City-level or global zones are future work.

**Q31: What if the grid API goes down?**  
**A:** CarbonEstimator caches responses for 5 minutes. If the API fails entirely, we can fall back to mock intensity so the scheduler still runs — degraded mode for demos.

---

### G. Demo, limitations & honesty

**Q32: What should we watch in your live demo?**  
**A:** The carbon intensity card — live API, job queue status transitions, carbon saved increasing, Greedy submitting and completing simulated jobs in a few minutes, and optional PPO policy switch.

**Q33: What are the main limitations?**  
**A:** Single machine; one job at a time; cost not implemented; PPO not fully tuned; benchmark uses synthetic jobs; cooperative pause not instant force-kill; India national grid only.

**Q34: What would you do differently with more time?**  
**A:** Add cost tracking, train PPO longer with better rewards, multi-node placement, GaiQ grade on the UI, and regional grid zones.

**Q35: If your demo fails on stage, what is your backup?**  
**A:** Swagger UI at `/docs` to submit jobs, pre-recorded screenshots, and benchmark JSON already generated. I can also run pytest to show tests pass.

---

### H. Critical / tough questions (prepare carefully)

**Q36: Is this just a timer that waits for night time?**  
**A:** No. We use real-time carbon intensity, not clock time. Carbon varies within the same hour based on grid mix. Our thresholds and PPO policy react to actual gCO₂/kWh, including forecast features for PPO training.

**Q37: Couldn't you just always train at 6 AM?**  
**A:** That is a naive schedule. Carbon varies day to day; deadlines may not allow waiting; and jobs have different priorities. Our scheduler decides per tick per job with constraints — more flexible than a fixed timetable.

**Q38: Your simulated jobs are fake — is the whole project fake?**  
**A:** The scheduler, API, grid feed, database, policies, and CodeCarbon path are real. Simulated jobs are a development and demo tool — like unit test workloads. We also implemented real ResNet and BERT training paths with measured emissions.

**Q39: How is this different from Kubernetes or SLURM?**  
**A:** Those are cluster resource managers — they allocate CPUs and GPUs. We solve a different problem — **when** to run based on **grid carbon**, with pause and resume and carbon accounting. We intentionally scoped to single-node; cluster integration is future work.

**Q40: What is your contribution vs existing tools like CodeCarbon?**  
**A:** CodeCarbon measures. We **schedule** — actively pause and resume to reduce emissions while respecting deadlines and training progress. That is the gap stated in our problem framing.

**Q41: Prove your system works.**  
**A:** I can show: live API returning real intensity; jobs transitioning QUEUED to RUNNING to COMPLETED; carbon_used_g increasing on real ResNet job; 36 passing tests; and benchmark JSON comparing Greedy vs PPO on the same carbon timeline.

**Q42: What was the hardest part?**  
**A:** Correct layer boundaries — orchestrator as sole writer, session carbon accumulation across pause and resume, single-flight evaluation so PPO actions match outcomes, and making the live demo reliable with WAL SQLite under concurrent API and tick writes.

---

### Quick revision card (5 bullets before viva)

1. **Problem:** Schedule ML training for greener grid periods  
2. **Core:** JobOrchestrator + Greedy (demo) + PPO (comparison)  
3. **Real:** Electricity Maps API + CodeCarbon + optional ResNet/BERT  
4. **Constraints:** Hard deadline + soft performance goal + carbon (Greedy thresholds / PPO learned)  
5. **Honest gaps:** No cost; single node; PPO under-tuned; simulated jobs for fast demo  

---

## Part 9 — Copy-paste command sheet

### Start everything
```bash
# Terminal 1
cd green-ai-scheduler/backend
export TICK_INTERVAL_SECONDS=5
PYTHONPATH=. uvicorn app.api.main:app --reload --port 8000

# Terminal 2
cd green-ai-scheduler/frontend
npm run dev
```

### Verify live API
```bash
curl -s http://localhost:8000/grid/status
curl -s http://localhost:8000/health
```

### Submit 5 simulated jobs (Greedy)
```bash
curl "http://localhost:8000/stats?policy=greedy"
curl -X POST http://localhost:8000/jobs/bulk \
  -H "Content-Type: application/json" \
  -d '{"count":5,"name_prefix":"demo","job_type":"simulated","total_epochs":2}'
```

### Submit 3 jobs under PPO
```bash
curl "http://localhost:8000/stats?policy=ppo"
curl -X POST http://localhost:8000/jobs/bulk \
  -H "Content-Type: application/json" \
  -d '{"count":3,"name_prefix":"ppo-demo","job_type":"simulated","total_epochs":2}'
```

### Watch progress
```bash
watch -n 2 'curl -s http://localhost:8000/stats?policy=greedy; echo; curl -s http://localhost:8000/jobs | python3 -c "import sys,json; [print(j[\"name\"], j[\"status\"], j[\"current_epoch\"]) for j in json.load(sys.stdin)]"'
```

### Offline benchmark (for slides)
```bash
cd green-ai-scheduler/backend
PYTHONPATH=.:.. python -m simulator.benchmark --policies greedy,ppo
```

### Run tests (if asked about quality)
```bash
cd green-ai-scheduler/backend
PYTHONPATH=.:.. pytest -q
```

---

## Part 10 — Troubleshooting during live demo

| Problem | What to do |
|---------|------------|
| Dashboard blank | Check frontend terminal; verify port 5173 |
| API errors | Check backend terminal; verify port 8000 |
| Jobs stuck QUEUED | Wait 10s per tick; or lower `TICK_INTERVAL_SECONDS` and restart backend |
| Carbon shows `mock` | Check `.env` API key; restart backend |
| 170MB download appears | A ResNet job started — use simulated only for demo |
| PPO same as Greedy | Normal if model missing; ensure `simulator/models/ppo_scheduler.zip` exists |
| Browser can't reach API | Frontend proxies `/api` → port 8000; keep both running |

**Emergency fallback:** Open http://localhost:8000/docs and run `POST /jobs` from Swagger UI while narrating.

---

## Part 11 — What to put on presentation slides

1. **Title** — Green Hours Scheduling for Sustainable AI Training  
2. **Problem** — Static training ignores grid cleanliness  
3. **Solution diagram** — submit → orchestrator → policy → run/pause  
4. **Architecture** — copy diagram from Part 3  
5. **Live screenshot** — dashboard with carbon card + job queue  
6. **Greedy vs PPO table** — benchmark numbers  
7. **PS alignment** — copy table from [DOCUMENTATION.md](DOCUMENTATION.md)  
8. **Scope** — cost descoped; single node; intensity vs renewable %  
9. **Future work** — multi-node, cost tracking, PPO tuning  

---

## Part 12 — Project completion summary (for panel)

| Area | Completion |
|------|------------|
| Core scheduling thesis | **~95%** |
| Deadline + performance constraints | **100%** |
| Cost constraint | **0%** (documented descope) |
| Engineering (code, tests, UI, docs) | **~90%** |
| **Overall PS alignment** | **~85–90%** — capstone-ready |

---

## Part 13 — File map for evaluators

```
green-ai-scheduler/
├── DEMO_GUIDE.md           ← this file (presentation)
├── RUNBOOK.md              ← technical run commands
├── DOCUMENTATION.md        ← architecture + PS table
├── REPORT.md               ← report bullets
├── backend/                ← Python FastAPI
├── frontend/               ← React dashboard
└── simulator/              ← PPO train + benchmark
```

---

*Good luck with your presentation. Lead with the live Greedy demo, be honest about scope, and keep simulated jobs for the main show — they're fast and reliable. Read Part 0 and Part 8 the night before your viva.*
