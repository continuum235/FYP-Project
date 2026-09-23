from simulator.scoring import ScoreConfig, score_results
from simulator.workload_generator import generate_workload


def test_workload_generation_is_reproducible():
    assert generate_workload(seed=42, horizon=200) == generate_workload(seed=42, horizon=200)
    assert generate_workload(seed=42, horizon=200) != generate_workload(seed=43, horizon=200)


def test_scoring_normalizes_each_comparison_set():
    results = {
        "greedy": {
            "total_carbon_g": 10,
            "deadline_satisfaction_percent": 90,
            "jobs_completed": 8,
            "performance_violations": 2,
            "average_pause_count": 3,
        },
        "ppo": {
            "total_carbon_g": 5,
            "deadline_satisfaction_percent": 100,
            "jobs_completed": 10,
            "performance_violations": 0,
            "average_pause_count": 1,
        },
    }
    config = ScoreConfig.from_dict({
        "carbon": 0.4,
        "deadline": 0.25,
        "throughput": 0.2,
        "performance": 0.1,
        "stability": 0.05,
    })
    scores = score_results(results, config)
    assert scores["ppo"] == 1.0
    assert scores["greedy"] == 0.0


def test_scoring_is_disabled_without_explicit_configuration():
    assert score_results({"greedy": {}}, None) == {"greedy": None}