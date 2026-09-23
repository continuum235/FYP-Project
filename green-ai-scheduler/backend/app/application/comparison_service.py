from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from simulator.benchmark import SUPPORTED_POLICIES, run_comparison


class ComparisonService:
    def __init__(self) -> None:
        self._path = Path(__file__).resolve().parents[2] / "simulator" / "logs" / "comparison_results.json"
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
        project_root = Path(__file__).resolve().parents[2]
        csv_path = project_root / "simulator" / "data" / "snapshots_2026-02-10_IN-2025-5_minute.csv"
        result = run_comparison(csv_path, normalized, horizon, seed, scoring)
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