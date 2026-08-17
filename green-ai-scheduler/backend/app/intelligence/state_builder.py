from typing import Optional

CLEAN_WINDOW_SENTINEL_HOURS = 48.0
FORECAST_STEP_HOURS = 5.0 / 60.0  # 5-minute forecast steps (Electricity Maps)


def forecast_avg_and_min(forecast: Optional[list[float]]) -> tuple[Optional[float], Optional[float]]:
    if not forecast:
        return None, None
    return sum(forecast) / len(forecast), min(forecast)


def time_to_clean_window_hours(
    forecast: Optional[list[float]],
    run_threshold: float,
    *,
    step_hours: float = FORECAST_STEP_HOURS,
    sentinel_hours: float = CLEAN_WINDOW_SENTINEL_HOURS,
) -> float:
    if not forecast:
        return sentinel_hours
    for i, intensity in enumerate(forecast):
        if intensity < run_threshold:
            return (i + 1) * step_hours
    return sentinel_hours


def progress_ratio(current_epoch: int, total_epochs: int) -> float:
    if total_epochs <= 0:
        return 0.0
    return min(1.0, max(0.0, current_epoch / total_epochs))
