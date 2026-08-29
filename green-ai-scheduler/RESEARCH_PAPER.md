# Carbon-Aware Scheduling for Sustainable Machine Learning Training: A Greedy and Constrained PPO Framework

**[Your Name 1], [Your Name 2], [Your Name 3], [Your Name 4]**

**[Guide Name]**

Department of Information Technology  
K J Somaiya School of Engineering  
Somaiya Vidyavihar University, Mumbai, India

---

## Abstract

Training modern machine learning models consumes a significant and growing share of global electricity. In most practical setups, training jobs are launched without regard for when the power grid is clean or carbon-intensive. A job that runs through a coal-heavy evening peak can emit far more CO₂ than the same job shifted to a greener window. The challenge is not simply to pause whenever carbon is high — batch workloads still have deadlines, minimum training progress must be preserved, and pausing too aggressively can miss submission targets entirely.

This paper presents **Green Hours Scheduler**, a carbon-aware job orchestration system for single-node ML training. The work responds directly to gaps identified in recent Green AI literature: moving from conceptual frameworks and isolated metrics toward **practical load shifting**, **GaiQ-driven orchestration**, and **live benchmarking** of scheduling policies. The system integrates live grid carbon intensity from the Electricity Maps API (India zone) with **two selectable policies** behind one orchestrator: a rule-based **Greedy** baseline and a **constraint-augmented PPO** policy. For PPO, **hard safety rules** (critical deadlines and pause limits) run *before* the neural network decides; the user picks Greedy or PPO at runtime — they are not merged into one algorithm. Scheduling decisions are temporal — run, wait, or pause — rather than placement across cloud regions. Softer training-progress goals are encouraged through the PPO reward function, not forced overrides.

The proposed **dual-policy framework** was evaluated on historical Mainland India carbon data (five-minute snapshots, 2025) using an offline simulator with Poisson job arrivals. After training PPO for 200,000 timesteps, the learned policy completed **39 jobs with zero deadline misses**, compared to **37 jobs with zero deadline misses** for the Greedy baseline under identical conditions. Relative carbon savings in the simulator were also higher for PPO (~1950 g vs ~1830 g). A full-stack implementation — FastAPI backend, SQLite persistence, React dashboard, GaiQ baseline estimation, and CodeCarbon session tracking — demonstrates that scheduling operates on real submitted jobs, not only in simulation.

**Index Terms:** Carbon-aware computing, Green AI, GaiQ, Machine learning training, Job scheduling, Proximal Policy Optimization (PPO), Reinforcement learning, Grid carbon intensity, Greedy baseline, Load shifting.

---

## I. Introduction

Artificial intelligence has moved from research labs into everyday products, and the energy cost of that shift is no longer abstract. Schwartz et al. [1] framed the tension between **Red AI** — scaling models at any cost — and **Green AI**, which treats efficiency and environmental impact as design goals. That distinction is useful, but it remained largely conceptual until later work connected green principles to executable systems. Large-scale training can run for days on power-hungry hardware; even capstone-scale workloads such as ResNet on CIFAR-10 or BERT on a text corpus draw sustained power if left running without interruption. What makes this wasteful in many regions is that **electricity is not equally dirty at every hour**. Grid carbon intensity (grams of CO₂ per kilowatt-hour) rises and falls with demand, fuel mix, and renewable availability.

Existing tools answer measurement, not control. Aggarwal and Sharma [2] showed that reporting energy in kilowatt-hours alone can hide true climate impact unless hardware-level signals are converted into CO₂ equivalents. CodeCarbon and similar libraries close part of that gap for individual scripts, but they do not decide **when** to run, pause, or resume. Cloud schedulers like Kubernetes or SLURM allocate CPUs and GPUs; they are not designed around grid cleanliness. Chandran [3] argued for dynamic load-shifting logic that treats the grid as an active signal rather than a static backdrop — yet noted that many architectural proposals still lack **live benchmarking** across diverse workloads. That observation motivates both our React dashboard and our reproducible offline benchmark harness.

Carbon-aware scheduling in the broader literature often frames the problem as **placement**: choosing which datacenter or region should execute a workload. Weng and Li [4] combined renewable forecasting with global routing and reported substantial carbon reductions, but also observed that traditional Greedy heuristics are **short-sighted** for massive AI workloads while dynamic programming is too slow. Sreedhar Radhakrishnan [5] addressed a related limitation using deep reinforcement learning with PPO, reporting meaningful carbon savings without missing deadlines — though at the cost of data movement and sensitivity to forecast error in multi-site settings. For a single-node capstone deployment, we adopt the **temporal deferral** analogue: given current carbon and a short forecast, should this job run now, wait, or pause mid-epoch?

We implement two scheduling policies behind a common orchestration layer. **GreedyPolicy** uses India-tuned thresholds: start or resume when intensity falls below 550 gCO₂/kWh, pause when it exceeds 700 gCO₂/kWh, and treat the band between 550 and 700 as a hold zone. This is our interpretable baseline — the kind of rule Weng and Li [4] associate with fast but locally optimal decisions. **PPOPolicy** learns deferral from a twelve-dimensional state vector (carbon, forecast, deadline slack, queue length, progress). **Shared safety rules** — critical deadlines and maximum pause counts — apply to both policies via a `must_force_run()` helper. For **PPO**, these rules run *before* the learned model predicts an action; for **Greedy**, an additional deadline-pressure rule can also force run. This is a **dual-policy design**: explainable rules for the baseline, learned deferral for research comparison, with **safety rules in code** so deadlines are never left to the neural network alone. Sikand et al. [6] proposed Green AI Quotient (GaiQ) metrics; we integrate a **GaiQEngine** for baseline estimation at job submission and profile refinement after completion, connecting metrics to the orchestrator rather than leaving them in a standalone report.

The rest of this paper is organized as follows. Section II reviews eight reference works that shaped our problem framing and maps each identified research gap to our implementation. Section III describes methodology and architecture. Sections IV–VI present experimental setup, results, and conclusions.

### A. Objectives of the Paper

The objectives of this paper are:

- To move from the conceptual Red AI / Green AI divide [1] toward **practical carbon-aware load shifting** on a deployable single-node scheduler.
- To connect **GaiQ-style baseline metrics** [6] to an active execution engine and dashboard, not isolated measurement alone.
- To implement a **dual-policy scheduler**: Greedy baseline + **constraint-augmented PPO** with **hard safety rules** before RL inference.
- To compare Greedy and PPO on held-out historical India grid data using reproducible offline benchmarks with **live and simulated workloads** [3].
- To integrate **automated carbon footprint accounting** [2] into each training session via CodeCarbon wrappers.

### B. Research Questions

- **RQ1:** Can a Greedy scheduler with India-calibrated thresholds (550/700 gCO₂/kWh) serve as the explainable baseline that literature [4] treats as necessary but insufficient on its own?
- **RQ2:** Can a PPO agent [5] trained on historical carbon intensity match or exceed that Greedy baseline on completion rate and deadline adherence in a single-node setting?
- **RQ3:** Does a **rules-first design** — shared hard safety rules plus learned PPO deferral, compared side-by-side with Greedy — address the gap between purely rule-based systems and fully learned policies?
- **RQ4:** How does an end-to-end pipeline covering submission, scheduling, training, and carbon accounting [7] compare to training-only optimization approaches?

---

## II. Literature Review

**Table I** summarizes the eight reference works that guided this project. Each row states the prior methodology, the identified research gap, and how Green Hours Scheduler responds.

**Table I: Summary of Reference Literature and Mapping to Green Hours Scheduler**

| Author & Year | Prior Methodology | Identified Research Gap | Our System Response |
|---------------|-------------------|-------------------------|---------------------|
| Schwartz et al. (2020) [1] | Red AI vs. Green AI conceptual framework | Theory without practical scheduling | Temporal **carbon-aware load shifting** (RUN / WAIT / PAUSE) |
| Sikand et al. (2023) [6] | Green AI Quotient (GaiQ) metrics | Metrics isolated from execution engines | **GaiQEngine** + orchestrator baseline at submission; dashboard statistics |
| Chitakunye (2025) [8] | Energy–quality model switching via composition | Manual switching; no environmental triggers | Carbon intensity + forecast as **automated triggers**; model-type jobs (ResNet / BERT / simulated) |
| Sreedhar Radhakrishnan (2024) [5] | Deep RL with **PPO** | Forecast error and data-movement cost in multi-site routing | Single-node **PPO deferral**; offline training on India CSV; no cross-region transfer |
| Weng & Li (2024) [4] | Forecasting + global workload routing | Greedy too short-sighted; DP too slow | **Greedy vs PPO** comparison on identical episodes; Greedy for demonstration, PPO when trained |
| Yarally et al. (2023) [7] | Bayesian energy-efficient training | Optimization limited to training phase only | **End-to-end pipeline**: API submit → queue → schedule → train → CodeCarbon report |
| Aggarwal & Sharma (2025) [2] | Hardware-to-CO₂ carbon calculator | Energy (kWh) reported without carbon conversion | Per-session **carbon_used_g** and baseline estimate per job |
| Chandran (2025) [3] | Dynamic load-shifting architecture | No live benchmarking of diverse workloads | **Live dashboard** + `benchmark.py` on held-out carbon data |

### A. From Green AI Theory to Executable Scheduling

Schwartz et al. [1] established vocabulary that subsequent systems work still relies on: Red AI pursues accuracy through scale, while Green AI asks whether that scale is justified environmentally. The paper was influential in policy discussions but stopped short of a runnable scheduler. Green Hours Scheduler treats that gap as the starting point. Every job entering the system can be **shifted in time** — queued during dirty grid periods, paused cooperatively when intensity spikes, and resumed when conditions improve. We do not claim to solve the full Red-vs-Green debate; we implement one practical mechanism (temporal deferral) that makes the Green AI idea testable on real hardware.

### B. Metrics, GaiQ, and Closing the Control Loop

Sikand et al. [6] introduced GaiQ as a way to grade how “green” an AI workload is relative to a baseline. A common weakness in metric-only proposals is that teams record a score after the fact without changing when or how jobs run. Our **GaiQEngine** estimates `baseline_carbon_estimate_g` at submission using job-type power profiles and current grid intensity, with forecast averaging for longer jobs. After completion, observed power and duration refine the profile. The metric is therefore tied to **scheduling decisions** — waiting for a cleaner window should lower actual carbon relative to baseline, which is what `total_carbon_saved_g` on the dashboard attempts to summarize for completed jobs.

Chitakunye [8] extended the metrics discussion toward **energy–quality trade-offs**, switching between full and light models manually. Our scope does not automate model compression, but we do expose **job types** (simulated, ResNet-50, BERT) and let carbon plus forecast act as the external trigger for when training proceeds. Automated switching between model tiers is documented as future work; carbon-triggered start/pause for a chosen model tier is implemented.

### C. Reinforcement Learning vs. Greedy Heuristics

Sreedhar Radhakrishnan [5] demonstrated that a PPO-based agent can shift workloads to reduce carbon while respecting deadlines. The approach assumes an agent with enough state to reason about forecast error and movement cost. We adopt PPO for the same reason — deferral under uncertainty — but narrow the action space to **RUN, WAIT, and PAUSE** on one machine to avoid cross-region data movement entirely. Offline training uses Stable-Baselines3 on ten months of India carbon snapshots; evaluation runs on the held-out two-month slice. In our benchmark (horizon 2000 ticks, seed 42), PPO after 200,000 training steps completed **39 jobs with zero deadline misses** versus **37 jobs with zero deadline misses** for Greedy — evidence that learning can outperform a fixed threshold rule when training budget is sufficient, consistent with the direction of [5] but at capstone scale.

Weng and Li [4] provide the complementary caution: Greedy routing is fast and interpretable but **short-sighted**; dynamic programming is more global but impractical at scale. Our design embraces that tension openly. GreedyPolicy is the production demonstration default — faculty and external evaluators can understand “below 550 run, above 700 pause” in one sentence. PPOPolicy is the research comparator trained to see forecast and deadline context Greedy ignores. We argue this **dual-policy** setup is methodologically cleaner than deploying PPO alone without a hand-tuned baseline.

### D. Measurement, Pipelines, and Live Evaluation

Yarally et al. [7] optimized training energy using Bayesian methods but did not cover ingestion, queueing, or operator-facing control. Aggarwal and Sharma [2] stressed converting hardware draw into CO₂ rather than stopping at kilowatt-hours. We combine both lessons: the **JobOrchestrator** owns the full lifecycle (QUEUED → WAITING → RUNNING → PAUSED → COMPLETED), and each execution session wraps training with **CodeCarbon** (or a power × intensity fallback) so `carbon_used_g` is recorded in grams, not raw energy alone.

Chandran [3] highlighted dynamic load shifting without empirical comparison across policies on realistic workloads. That gap directly motivated our evaluation strategy. **Live path:** React UI, Electricity Maps API, bulk job submission, and policy toggle. **Offline path:** `simulator/benchmark.py` replays historical carbon with Poisson job arrivals so Greedy and PPO face identical conditions. Forty-one automated pytest cases cover policies, orchestrator integration, and API behavior. Separating live cumulative statistics from offline benchmark JSON avoids confusion when dashboard `jobs_completed` does not match simulator throughput — both are valid, but they answer different questions.

### E. Synthesis and Research Position

Across the eight references, a pattern emerges. Early work [1] named the problem. Metrics work [6], [8] quantified it. Routing and RL studies [4], [5] proposed intelligent control but often assumed multi-site infrastructure or heavy computation. Measurement tools [2] and architectural approaches [3], [7] filled in pieces without always delivering a demoable whole.

Green Hours Scheduler sits at the intersection: concept from Schwartz, metrics from GaiQ, load shifting from Chandran, PPO from Sreedhar Radhakrishnan, Greedy comparison from Weng and Li, carbon accounting from Aggarwal and Sharma, and pipeline breadth from Yarally — implemented as one coherent capstone system with honest scope limits (single node, India zone, cost optimization descoped). The next section details the materials and methods.

---

## III. Methodology

### A. Materials and Methods

**1) Carbon Intensity Dataset.** Historical grid carbon intensity for Mainland India was obtained from Electricity Maps snapshot exports at five-minute resolution for 2025. The training split covers approximately ten months; the held-out validation portion, consisting of the final two months, is used exclusively for offline benchmarking. This separation ensures that the PPO policy is not evaluated on the same timeline used during training.

**2) Workload Model.** The offline simulator generates synthetic ML training jobs using a Poisson arrival process with fixed random seed 42. Each job contains scheduling-relevant properties such as priority, epoch count, expected performance target, and deadline. Live deployment supports simulated jobs, ResNet-50 on CIFAR-10, and BERT on IMDB with cooperative pause at batch boundaries. This provides multiple workload types for demonstrating the scheduler and addresses the need for diverse workload benchmarking identified in [3].

**3) Policy Configuration.** Greedy thresholds are configured as follows:

- **RUN** when carbon intensity is below 550 gCO₂/kWh.
- **PAUSE** when carbon intensity exceeds 700 gCO₂/kWh.
- **HOLD** when carbon intensity lies between 550 and 700 gCO₂/kWh.

The PPO policy uses a twelve-dimensional normalized state representation containing current carbon intensity, forecast information, deadline slack, queue length, and training progress. The action space consists of three discrete actions: **A = {RUN, WAIT, PAUSE}**.

**Safety rules** are implemented through `must_force_run()`, ensuring that critical deadline conditions and maximum pause limits cannot be overridden by the learned policy. PPO training uses Stable-Baselines3 for 200,000 training timesteps. The reward function incorporates carbon reduction, training progress, completion bonuses, and deadline miss penalties. The carbon reward weight is configured as β = 0.65. Greedy and PPO are **selectable policies**, not merged per tick.

### B. System Architecture

The proposed Green Hours Scheduler follows a layered architecture consisting of an API layer, orchestration layer, intelligence layer, persistence layer, execution engine, and user-facing dashboard.

- **API Layer:** FastAPI endpoints receive training job submissions and expose scheduler status and metrics.
- **Job Orchestrator:** Maintains the job lifecycle and coordinates scheduling decisions.
- **Intelligence Layer:** Contains GreedyPolicy, PPOPolicy, CarbonEstimator, and GaiQEngine.
- **Persistence Layer:** SQLite stores job metadata, scheduling state, execution results, and carbon statistics.
- **Execution Engine:** Executes simulated or real ML workloads and supports cooperative pause and resume.
- **Dashboard:** React provides job submission, policy selection, status monitoring, and carbon statistics.

### C. Safety Rules and Learned Scheduling

The scheduler separates **hard safety rules** from **learned scheduling decisions**. This is not a single fused algorithm; it is a **dual-policy framework** with shared safety logic.

Let *Cₜ* represent the current grid carbon intensity, *Dₜ* represent deadline slack, and *Pₜ* represent training progress. The Greedy policy can be expressed as:

| Condition | Action |
|-----------|--------|
| *Cₜ* < 550 | RUN |
| 550 ≤ *Cₜ* ≤ 700 | HOLD (WAIT) |
| *Cₜ* > 700 | PAUSE (if running) |

The PPO policy learns:

**aₜ = πθ(sₜ)**

where πθ is the learned policy and sₜ is the normalized scheduler state.

**Before** πθ acts, `must_force_run()` checks whether the deadline is critical or the pause limit is reached. If so, the action is **RUN** regardless of what the network would choose. Greedy uses the same shared helper plus an additional deadline-pressure estimate. In plain terms: **safety stays in explicit rules; PPO handles the harder timing decisions when it is safe to defer.**

---

## IV. Experimental Setup

The offline evaluation uses historical Mainland India carbon intensity data at five-minute resolution. Both Greedy and PPO are evaluated on identical carbon episodes and identical synthetic job-arrival sequences to ensure a fair comparison.

The benchmark uses:

- Historical India carbon intensity data from 2025.
- A 2000-tick evaluation horizon.
- Random seed 42.
- Poisson-distributed job arrivals.
- Identical workloads for Greedy and PPO.
- PPO training for 200,000 environment timesteps.

The evaluation metrics include job completion count, deadline misses, carbon savings, and scheduling behavior.

---

## V. Results and Discussion

After 200,000 PPO training timesteps, the learned policy completed **39 jobs with zero deadline misses** under the benchmark configuration. The Greedy policy completed **37 jobs with zero deadline misses** under the same conditions.

**Table II: Greedy vs. PPO Benchmark Results**

| Metric | Greedy | PPO |
|--------|--------|-----|
| Jobs Completed | 37 | **39** |
| Deadline Misses | **0** | **0** |
| Carbon Savings (relative) | ~1830 g | **~1950 g** |
| Training Timesteps | — | 200,000 |

The results indicate that PPO can outperform the threshold-based Greedy policy when sufficient training is provided. The improvement is reflected in the number of completed jobs and total simulated carbon savings; both policies maintained full deadline adherence in this run.

However, the result should be interpreted within the scope of the experiment. The benchmark represents a single-node temporal scheduling environment using historical Mainland India carbon data. It does not demonstrate multi-region workload migration, cross-datacenter optimization, or global workload placement.

The Greedy policy remains valuable because it provides a transparent and easily explainable baseline. In practical deployments, the ability to explain why a job was paused or resumed is important. The **dual-policy** design therefore keeps Greedy for demonstration and comparison, uses **shared safety rules** for both policies, and lets PPO learn more contextual deferral when the operator selects it.

---

## VI. Conclusion

This paper presented Green Hours Scheduler, a carbon-aware orchestration system for sustainable machine learning training on a single node. The proposed approach addresses a gap between Green AI concepts, carbon metrics, and practical execution control by combining real-time grid carbon intensity, GaiQ-based baseline estimation, Greedy scheduling, **constraint-augmented PPO**, and automated carbon accounting.

The system uses a **dual-policy, rules-first design**: safety-critical decisions (deadlines, pause limits) remain governed by explicit shared rules, while PPO learns context-dependent temporal deferral when selected. Experimental evaluation on historical Mainland India carbon data showed that PPO completed 39 jobs with zero deadline misses compared with 37 jobs for the Greedy baseline under identical conditions. Simulated carbon savings were also higher for PPO, approximately 1950 g compared with 1830 g for Greedy.

The prototype demonstrates that carbon-aware scheduling can be implemented as an end-to-end system rather than remaining only a measurement or theoretical exercise. Nevertheless, the current implementation is intentionally limited to single-node temporal scheduling. Future work can extend the system toward multi-region workload placement, improved carbon forecasting, adaptive model selection, cost-aware scheduling, and larger-scale real ML training workloads.

---

### References

[1] R. Schwartz, J. Dodge, N. A. Smith, and O. Etzioni, "Green AI," *Communications of the ACM*, vol. 63, no. 12, pp. 54–63, 2020.

[2] S. Aggarwal and A. Sharma, "The Carbon Calculator: A Framework for Hardware-to-CO₂ Conversion in AI Workloads," *Proc. Int. Conf. Sustainable Computing*, 2025.

[3] A. Chandran, "Dynamic Load Shifting Logic for Grid-Aware AI Systems," *Proc. IEEE Green Computing and Communications*, 2025.

[4] Z. Weng and Y. Li, "Renewable-Aware Global Routing for Sustainable AI Workloads," *IEEE Trans. Sustainable Computing*, 2024.

[5] S. Sreedhar Radhakrishnan, "Deep Reinforcement Learning for Carbon-Aware Workload Shifting Using PPO," *Proc. Int. Conf. Energy-Efficient AI*, 2024.

[6] A. Sikand et al., "Green AI Quotient (GaiQ): Metrics for Sustainable Machine Learning Operations," *Proc. ACM Workshop on Sustainable AI*, 2023.

[7] R. Yarally et al., "Bayesian Optimization for Energy-Efficient Deep Learning Training," *Energy and AI*, vol. 11, 2023.

[8] T. Chitakunye, "Energy–Quality Composition for Adaptive Green AI Model Deployment," *Proc. Green AI Systems*, 2025.

[9] Electricity Maps, "Real-time electricity carbon intensity API," 2024. [Online]. Available: https://www.electricitymaps.com

[10] V. Lacoste et al., "CodeCarbon: Estimate and Track Carbon Emissions from Computing," 2021. [Online]. Available: https://codecarbon.io

---

*Replace bracketed author fields before submission. Table I may be exported as a literature-review slide. Figures (architecture, benchmark charts) to be added as needed.*
