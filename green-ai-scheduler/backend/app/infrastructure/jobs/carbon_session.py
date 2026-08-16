"""CodeCarbon session wrapper — one tracker per training session (pause/resume = new session)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass
class CarbonSessionResult:
    session_carbon_g: float
    session_energy_kwh: float
    session_duration_hours: float
    used_codecarbon: bool


@contextmanager
def carbon_training_session(
    job_id: int,
    *,
    power_kw_fallback: float = 0.15,
    intensity_g_per_kwh_fallback: float = 500.0,
) -> Iterator[CarbonSessionResult]:
    """
    Start CodeCarbon for this session; on exit fill session carbon/energy.
    Falls back to duration × power estimate if CodeCarbon unavailable.
    """
    start = time.time()
    tracker = None
    used_codecarbon = False
    result = CarbonSessionResult(0.0, 0.0, 0.0, False)

    try:
        from codecarbon import EmissionsTracker

        tracker = EmissionsTracker(
            project_name=f"green_scheduler_job_{job_id}",
            save_to_file=False,
            allow_multiple_runs=True,
        )
        tracker.start()
        used_codecarbon = True
    except Exception:
        tracker = None

    try:
        yield result
    finally:
        duration_hours = max((time.time() - start) / 3600.0, 1e-9)
        result.session_duration_hours = duration_hours

        if tracker is not None:
            try:
                emissions_kg = tracker.stop()
                result.session_carbon_g = float(emissions_kg) * 1000.0
                result.used_codecarbon = True
                energy = getattr(tracker, "_total_energy", None)
                if energy is not None and hasattr(energy, "kWh"):
                    result.session_energy_kwh = float(energy.kWh())
                elif hasattr(tracker, "final_emissions_data"):
                    data = tracker.final_emissions_data
                    if data is not None and hasattr(data, "energy_consumed"):
                        result.session_energy_kwh = float(data.energy_consumed)
                if result.session_energy_kwh <= 0 and duration_hours > 0:
                    result.session_energy_kwh = power_kw_fallback * duration_hours
            except Exception:
                result.session_energy_kwh = power_kw_fallback * duration_hours
                result.session_carbon_g = result.session_energy_kwh * intensity_g_per_kwh_fallback
                result.used_codecarbon = False
        else:
            result.session_energy_kwh = power_kw_fallback * duration_hours
            result.session_carbon_g = result.session_energy_kwh * intensity_g_per_kwh_fallback
            result.used_codecarbon = False
