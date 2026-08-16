from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env from green-ai-scheduler/ regardless of cwd (backend/ vs root)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./green_scheduler.db"
    electricity_maps_api_key: str = ""
    electricity_maps_zone: str = "IN"
    scheduling_policy: str = "greedy"
    tick_interval_seconds: int = 60
    greedy_run_threshold: float = 450.0
    greedy_pause_threshold: float = 550.0
    greedy_max_pause_count: int = 10
    greedy_deadline_safety_margin_hours: float = 0.5
    carbon_cache_ttl_seconds: int = 300
    checkpoint_dir: str = "./checkpoints"
    ppo_model_path: str = "../simulator/models/ppo_scheduler.zip"

    def __init__(self, **kwargs):
        import os
        super().__init__(**kwargs)
        # Accept legacy/alternate env var names
        if not self.electricity_maps_api_key:
            self.electricity_maps_api_key = os.getenv(
                "ELECTRICITY_MAPS_API_KEY",
                os.getenv("ELECTRICITY_MAP_API", ""),
            )
        if os.getenv("DATABASE_URL"):
            self.database_url = os.environ["DATABASE_URL"]
        if os.getenv("CHECKPOINT_DIR"):
            self.checkpoint_dir = os.environ["CHECKPOINT_DIR"]
        if os.getenv("TICK_INTERVAL_SECONDS"):
            self.tick_interval_seconds = int(os.environ["TICK_INTERVAL_SECONDS"])


settings = Settings()
