import time
from typing import Optional

import httpx

from app.domain.models import GridStatus


class CarbonEstimator:
    """Wraps Electricity Maps API with 5-minute cache. Falls back to mock when no API key."""

    def __init__(
        self,
        api_key: str,
        zone: str = "IN",
        cache_ttl_seconds: int = 300,
        mock_intensity: float = 500.0,
    ) -> None:
        self._api_key = api_key
        self._zone = zone
        self._cache_ttl = cache_ttl_seconds
        self._mock_intensity = mock_intensity
        self._cached_intensity: Optional[float] = None
        self._cached_forecast: Optional[list[float]] = None
        self._cache_time: float = 0.0

    def _is_cache_valid(self) -> bool:
        return (time.time() - self._cache_time) < self._cache_ttl

    async def get_current_intensity(self) -> GridStatus:
        if self._is_cache_valid() and self._cached_intensity is not None:
            return GridStatus(
                carbon_intensity_g_per_kwh=self._cached_intensity,
                source="electricity_maps" if self._api_key else "mock",
                zone=self._zone,
                cached=True,
            )

        if not self._api_key:
            self._cached_intensity = self._mock_intensity
            self._cache_time = time.time()
            return GridStatus(
                carbon_intensity_g_per_kwh=self._mock_intensity,
                source="mock",
                zone=self._zone,
                cached=False,
            )

        url = f"https://api.electricitymap.org/v3/carbon-intensity/latest"
        headers = {"auth-token": self._api_key}
        params = {"zone": self._zone}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            intensity = float(data.get("carbonIntensity", self._mock_intensity))

        self._cached_intensity = intensity
        self._cache_time = time.time()
        return GridStatus(
            carbon_intensity_g_per_kwh=intensity,
            source="electricity_maps",
            zone=self._zone,
            cached=False,
        )

    async def get_forecast(self, window_hours: float = 6.0) -> Optional[list[float]]:
        if self._is_cache_valid() and self._cached_forecast is not None:
            return self._cached_forecast

        if not self._api_key:
            base = self._mock_intensity
            self._cached_forecast = [base * (0.9 + 0.1 * (i % 3)) for i in range(12)]
            self._cache_time = time.time()
            return self._cached_forecast

        url = "https://api.electricitymap.org/v3/carbon-intensity/forecast"
        headers = {"auth-token": self._api_key}
        params = {"zone": self._zone}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                forecast = [
                    float(p["carbonIntensity"])
                    for p in data.get("forecast", [])[: int(window_hours * 12)]
                ]
                if forecast:
                    self._cached_forecast = forecast
                    self._cache_time = time.time()
                    return forecast
        except httpx.HTTPError:
            pass
        return None

    def set_mock_intensity(self, intensity: float) -> None:
        """Test helper to override intensity without API."""
        self._cached_intensity = intensity
        self._cache_time = time.time()
