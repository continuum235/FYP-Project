"""Train PPO scheduler on historical carbon intensity data."""

from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env

from app.domain.enums import Action
from app.domain.models import SchedulingState
from app.intelligence.policies.greedy import GreedyPolicy
from app.intelligence.policies.ppo_policy import CARBON_MAX, CARBON_MIN, state_to_obs
from simulator.benchmark import SchedulingSimulator, load_carbon_csv

OBS_SIZE = 8


class SchedulerEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, carbon_series: np.ndarray, horizon: int = 500) -> None:
        super().__init__()
        self.carbon_series = carbon_series
        self.horizon = horizon
        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(low=0, high=1, shape=(OBS_SIZE,), dtype=np.float32)
        self.sim: SchedulingSimulator | None = None
        self._step = 0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.sim = SchedulingSimulator(
            carbon_series=self.carbon_series,
            policy=GreedyPolicy(run_threshold=450.0, pause_threshold=550.0),
        )
        self.sim.add_poisson_arrivals(rate=0.05, horizon=self.horizon)
        self._step = 0
        job = self.sim._select_candidate()
        obs = state_to_obs(self.sim._build_state(job)) if job else np.zeros(OBS_SIZE, dtype=np.float32)
        return obs, {}

    def step(self, action_idx: int):
        assert self.sim is not None
        job = self.sim._select_candidate()
        if job is None:
            return np.zeros(OBS_SIZE, dtype=np.float32), 0.0, True, False, {}

        action = {0: Action.RUN, 1: Action.WAIT, 2: Action.PAUSE}[int(action_idx)]
        reward = 0.0
        pre_carbon = job.carbon_used_g

        if self.sim.running_job:
            if action in (Action.WAIT, Action.PAUSE):
                if job.current_epoch < job.performance_target:
                    reward -= 5.0
                job.pause_count += 1
                job.status = "PAUSED"
                self.sim.running_job = None
                reward -= 0.1
            else:
                job.current_epoch += 1
                intensity = self.sim._intensity_at(self.sim.current_tick)
                job.carbon_used_g += 0.05 * intensity / 500
                reward -= job.carbon_used_g - pre_carbon
                if job.current_epoch >= job.total_epochs:
                    job.status = "COMPLETED"
                    self.sim.running_job = None
                    if intensity < 450:
                        reward += 1.0
        else:
            if action == Action.RUN:
                job.status = "RUNNING"
                self.sim.running_job = job
                reward += 0.5
            else:
                reward -= 0.05
                if job.current_epoch < job.performance_target:
                    reward -= 2.0

        self.sim.current_tick += 1
        self._step += 1
        done = self._step >= self.horizon
        next_job = self.sim._select_candidate()
        obs = state_to_obs(self.sim._build_state(next_job)) if next_job else np.zeros(OBS_SIZE, dtype=np.float32)
        return obs, reward, done, False, {}


def make_env(carbon_series: np.ndarray, horizon: int = 500) -> SchedulerEnv:
    return SchedulerEnv(carbon_series, horizon)


def train(output_dir: Path | None = None, timesteps: int = 50000) -> Path:
    output_dir = output_dir or Path(__file__).parent / "models"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    csv_path = Path(__file__).parent / "data" / "snapshots_2026-02-10_IN-2025-5_minute.csv"
    carbon = load_carbon_csv(csv_path, validation_only=False)
    split = int(len(carbon) * 10 / 12)
    train_carbon = carbon[:split]

    env = make_env(train_carbon, horizon=300)
    check_env(env)
    model = PPO("MlpPolicy", env, verbose=0, n_steps=256, batch_size=64)
    model.learn(total_timesteps=timesteps)

    model_path = output_dir / "ppo_scheduler.zip"
    model.save(str(model_path))

    try:
        import matplotlib.pyplot as plt

        rewards = model.ep_info_buffer if hasattr(model, "ep_info_buffer") else []
        if rewards:
            plt.figure()
            plt.plot([r["r"] for r in rewards])
            plt.xlabel("Episode")
            plt.ylabel("Reward")
            plt.title("PPO Training Reward")
            plt.savefig(log_dir / "training_curves.png")
            plt.close()
    except ImportError:
        pass

    return model_path


if __name__ == "__main__":
    path = train()
    print(f"Model saved to {path}")
