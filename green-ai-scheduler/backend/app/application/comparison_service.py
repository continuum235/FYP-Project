from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from simulator.benchmark import SUPPORTED_POLICIES, run_comparison

# backend/app/application/comparison_service.py -> parents[2] is backend/, parents[3] is the project root.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
CARBON_DATASET_NAME = "snapshots_2026-02-10_IN-2025-5_minute.csv"
# The carbon dataset lives in the top-level simulator package, NOT in backend/simulator/.
DEFAULT_CARBON_DATASET_PATH = PROJECT_ROOT / "simulator" / "data" / CARBON_DATASET_NAME
COMPARISON_RESULTS_PATH = BACKEND_ROOT / "simulator" / "logs" / "comparison_results.json"


class ComparisonService:
    def __init__(self, results_path: Path | None = None, carbon_dataset_path: Path | None = None) -> None:
        self._path = Path(results_path) if results_path is not None else COMPARISON_RESULTS_PATH
        self._carbon_dataset_path = (
            Path(carbon_dataset_path) if carbon_dataset_path is not None else DEFAULT_CARBON_DATASET_PATH
        )
        self._runs: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        try:
            values = json.loads(self._path.read_text())
            return {run["run_id"]: run for run in values}
        except (OSError, ValueError, KeyError, TypeError):
            return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(list(self._runs.values()), indent=2, default=str))

    def run(self, policies: list[str], horizon: int, seed: int, scoring: dict | None) -> str:
        normalized = [name.strip().lower().replace("-", "_").replace(" ", "_") for name in policies]
        if len(set(normalized)) != len(normalized):
            raise ValueError("policies must be unique")
        invalid = [name for name in normalized if name not in SUPPORTED_POLICIES]
        if invalid:
            raise ValueError(f"unsupported policies: {', '.join(invalid)}")
        if not self._carbon_dataset_path.is_file():
            raise FileNotFoundError(
                f"carbon dataset not found at {self._carbon_dataset_path}; "
                "refusing to benchmark against random carbon data"
            )
        result = run_comparison(self._carbon_dataset_path, normalized, horizon, seed, scoring)
        run_id = f"benchmark_{uuid4().hex[:12]}"
        self._runs[run_id] = {
            "run_id": run_id,
            "status": "completed",
            "created_at": datetime.now(timezone.utc),
            "result": result,
        }
        self._save()
        return run_id

    def get(self, run_id: str) -> dict | None:
        return self._runs.get(run_id)

    def list(self) -> list[dict]:
        return list(reversed(list(self._runs.values())))