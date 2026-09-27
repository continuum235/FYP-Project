from pathlib import Path

import pytest

from app.application.comparison_service import (
    BACKEND_ROOT,
    CARBON_DATASET_NAME,
    DEFAULT_CARBON_DATASET_PATH,
    PROJECT_ROOT,
    ComparisonService,
)
from simulator.benchmark import load_carbon_csv
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


def test_comparison_service_uses_top_level_simulator_dataset():
    assert PROJECT_ROOT == BACKEND_ROOT.parent
    assert DEFAULT_CARBON_DATASET_PATH == PROJECT_ROOT / "simulator" / "data" / CARBON_DATASET_NAME
    assert DEFAULT_CARBON_DATASET_PATH.is_file()


def test_comparison_service_does_not_look_for_dataset_under_backend():
    assert not (BACKEND_ROOT / "simulator" / "data" / CARBON_DATASET_NAME).exists()


def test_carbon_loader_reads_real_dataset_instead_of_random_fallback():
    series = load_carbon_csv(DEFAULT_CARBON_DATASET_PATH)
    assert series.size > 5000
    assert 100.0 < series.min() and series.max() < 1200.0


def test_carbon_loader_raises_instead_of_returning_random_data(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_carbon_csv(tmp_path / "snapshots_missing.csv")


def test_carbon_loader_raises_on_dataset_without_carbon_column(tmp_path):
    unusable = tmp_path / "unusable.csv"
    unusable.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        load_carbon_csv(unusable)


def test_comparison_service_run_reports_missing_dataset(tmp_path):
    service = ComparisonService(
        results_path=tmp_path / "comparison_results.json",
        carbon_dataset_path=tmp_path / "missing.csv",
    )
    with pytest.raises(FileNotFoundError):
        service.run(["greedy"], horizon=50, seed=1, scoring=None)


def test_comparison_service_run_records_real_dataset_path(tmp_path):
    service = ComparisonService(results_path=tmp_path / "comparison_results.json")
    run_id = service.run(["greedy"], horizon=50, seed=1, scoring=None)
    stored = service.get(run_id)
    assert stored is not None
    assert Path(stored["result"]["config"]["dataset"]) == DEFAULT_CARBON_DATASET_PATH
    assert stored["result"]["policies"]["greedy"]["average_carbon_intensity"] > 0.0
