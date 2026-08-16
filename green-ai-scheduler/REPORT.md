# Green Hours Scheduling — Final Report Notes

## Problem statement alignment

| Requirement | Implementation |
|-------------|----------------|
| Reduce carbon footprint via scheduling | GreedyPolicy + PPOPolicy pause/resume during high-carbon windows |
| High renewable / clean grid periods | Carbon intensity (gCO₂/kWh) from Electricity Maps |
| Deadline constraints | GreedyPolicy deadline-proximity RUN-forcing |
| Performance constraints | `performance_target` min-epoch floor before pause |
| Cost constraints | **Descoped** — documented intentional milestone cut |

## Carbon signal choice

We use carbon intensity rather than renewable percentage because it is the standard actionable signal for scheduling, matches Electricity Maps API and the PPO training CSV, and distinguishes low-carbon nuclear grids from high-renewable profiles.

## Greedy vs PPO evaluation

- **Layer A:** Parametric pytest — both policies pass scheduling invariant tests
- **Layer B:** Offline simulator benchmark on held-out validation months of India 2025 carbon data
- Metrics: carbon saved, deadline misses, performance violations, pause count, throughput

## Scope limitations

- Single-node (one RUNNING job max)
- India national grid (`IN`), not regional
- Cooperative pause bounded by batch compute time
- Cost optimization not implemented
