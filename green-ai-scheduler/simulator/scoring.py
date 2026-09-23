from dataclasses import dataclass


DEFAULT_WEIGHTS = {
    "carbon": 0.40,
    "deadline": 0.25,
    "throughput": 0.20,
    "performance": 0.10,
    "stability": 0.05,
}


@dataclass(frozen=True)
class ScoreConfig:
    weights: dict[str, float]

    @classmethod
    def from_dict(cls, value: dict[str, float] | None) -> "ScoreConfig | None":
        if value is None:
            return None
        weights = {key: float(weight) for key, weight in value.items()}
        if set(weights) != set(DEFAULT_WEIGHTS) or any(weight < 0 for weight in weights.values()):
            raise ValueError("weights must contain carbon, deadline, throughput, performance, and stability")
        if abs(sum(weights.values()) - 1.0) > 1e-6:
            raise ValueError("scoring weights must sum to 1")
        return cls(weights)


def _normalize(values: list[float], higher_is_better: bool) -> list[float]:
    low, high = min(values), max(values)
    if high == low:
        return [1.0] * len(values)
    if higher_is_better:
        return [(value - low) / (high - low) for value in values]
    return [(high - value) / (high - low) for value in values]


def score_results(results: dict[str, dict], config: ScoreConfig | None) -> dict[str, float | None]:
    scores = {policy: None for policy in results}
    if config is None or not results:
        return scores
    rows = list(results.values())
    dimensions = {
        "carbon": _normalize([row["total_carbon_g"] for row in rows], False),
        "deadline": _normalize([row["deadline_satisfaction_percent"] for row in rows], True),
        "throughput": _normalize([row["jobs_completed"] for row in rows], True),
        "performance": _normalize([row["performance_violations"] for row in rows], False),
        "stability": _normalize([row["average_pause_count"] for row in rows], False),
    }
    for index, policy in enumerate(results):
        scores[policy] = sum(config.weights[name] * dimensions[name][index] for name in dimensions)
    return scores