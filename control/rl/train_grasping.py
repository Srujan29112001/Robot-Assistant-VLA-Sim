"""
PPO-based Reinforcement Learning for Robotic Grasping
Train adaptive grasping policies using Stable-Baselines3
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
import torch
import logging
from typing import Dict, Tuple, Any
import wandb
from wandb.integration.sb3 import WandbCallback

logger = logging.getLogger(__name__)


class GraspingEnv(gym.Env):
    """
    Robotic Grasping Environment
    Simulates gripper approaching and grasping an object
    """

    def __init__(self, render_mode=None):
        super().__init__()

        # Action space: [gripper_x_velocity, gripper_y_velocity, gripper_z_velocity, gripper_close]
        self.action_space = spaces.Box(
            low=np.array([-1.0, -1.0, -1.0, 0.0]),
            high=np.array([1.0, 1.0, 1.0, 1.0]),
            dtype=np.float32
        )

        # Observation space: [gripper_pos(3), object_pos(3), object_detected(1), contact_force(1)]
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(8,),
            dtype=np.float32
        )

        # State
        self.gripper_pos = np.array([0.0, 0.0, 0.5])  # Above table
        self.object_pos = np.array([0.0, 0.0, 0.0])  # On table
        self.object_grasped = False
        self.contact_force = 0.0
        self.step_count = 0
        self.max_steps = 200

        self.render_mode = render_mode

        # Gripper state
        self.gripper_open = 1.0  # 1.0 = fully open, 0.0 = closed

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        # Randomize object position
        self.object_pos = np.array([
            np.random.uniform(-0.15, 0.15),
            np.random.uniform(-0.15, 0.15),
            np.random.uniform(0.0, 0.05)  # Small height variation
        ])

        # Reset gripper to random start position
        self.gripper_pos = np.array([
            np.random.uniform(-0.2, 0.2),
            np.random.uniform(-0.2, 0.2),
            np.random.uniform(0.3, 0.6)
        ])

        self.object_grasped = False
        self.contact_force = 0.0
        self.step_count = 0
        self.gripper_open = 1.0

        return self._get_obs(), {}

    def _get_obs(self) -> np.ndarray:
        """Get current observation"""
        object_detected = 1.0 if np.linalg.norm(self.gripper_pos - self.object_pos) < 0.1 else 0.0

        obs = np.concatenate([
            self.gripper_pos,
            self.object_pos,
            [object_detected],
            [self.contact_force]
        ])

        return obs.astype(np.float32)

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Execute one step"""
        self.step_count += 1

        # Parse action
        gripper_velocity = action[:3] * 0.01  # Scale down velocity
        gripper_close_action = action[3]

        # Update gripper position
        self.gripper_pos += gripper_velocity
        self.gripper_pos = np.clip(self.gripper_pos, [-0.3, -0.3, 0.0], [0.3, 0.3, 0.7])

        # Update gripper state
        if gripper_close_action > 0.5:
            self.gripper_open = max(0.0, self.gripper_open - 0.1)
        else:
            self.gripper_open = min(1.0, self.gripper_open + 0.1)

        # Check for contact/grasp
        distance_to_object = np.linalg.norm(self.gripper_pos - self.object_pos)

        # Compute reward
        reward = 0.0

        # Reward for approaching object
        reward -= distance_to_object * 0.1

        # Reward for being close with gripper closed
        if distance_to_object < 0.05:
            self.contact_force = 1.0
            if self.gripper_open < 0.3:  # Gripper mostly closed
                self.object_grasped = True
                reward += 100.0  # Large reward for successful grasp
            else:
                reward += 5.0  # Small reward for being close
        else:
            self.contact_force = 0.0

        # Penalty for keeping gripper closed when far
        if self.gripper_open < 0.5 and distance_to_object > 0.1:
            reward -= 1.0

        # Time penalty
        reward -= 0.01

        # Check termination
        terminated = self.object_grasped
        truncated = self.step_count >= self.max_steps

        return self._get_obs(), reward, terminated, truncated, {}

    def render(self):
        """Render environment (placeholder)"""
        if self.render_mode == "human":
            print(f"Gripper: {self.gripper_pos}, Object: {self.object_pos}, Grasped: {self.object_grasped}")


class GraspingTrainer:
    """
    Trainer for robotic grasping using PPO
    """

    def __init__(
        self,
        env_id: str = "GraspingEnv-v0",
        num_envs: int = 4,
        use_wandb: bool = True
    ):
        # Register environment
        gym.register(id=env_id, entry_point=GraspingEnv)

        self.env_id = env_id
        self.num_envs = num_envs
        self.use_wandb = use_wandb

        # Create vectorized environment
        self.env = SubprocVecEnv([
            lambda: Monitor(gym.make(env_id)) for _ in range(num_envs)
        ])

        # Evaluation environment
        self.eval_env = Monitor(gym.make(env_id))

        logger.info(f"Created {num_envs} training environments")

    def train(
        self,
        total_timesteps: int = 500_000,
        learning_rate: float = 3e-4,
        n_steps: int = 2048,
        batch_size: int = 64,
        checkpoint_freq: int = 50_000,
        output_dir: str = "./rl_checkpoints/grasping"
    ):
        """
        Train PPO grasping policy

        Args:
            total_timesteps: Total training timesteps
            learning_rate: Learning rate
            n_steps: Steps per rollout
            batch_size: Batch size
            checkpoint_freq: Checkpoint frequency
            output_dir: Output directory
        """
        # Initialize W&B
        if self.use_wandb:
            run = wandb.init(
                project="vla-robot-grasping",
                config={
                    "algorithm": "PPO",
                    "env": self.env_id,
                    "total_timesteps": total_timesteps,
                    "learning_rate": learning_rate,
                },
                sync_tensorboard=True,
                monitor_gym=True
            )

        # Initialize PPO model
        model = PPO(
            "MlpPolicy",
            self.env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
            vf_coef=0.5,
            max_grad_norm=0.5,
            tensorboard_log=f"{output_dir}/tensorboard",
            verbose=1,
        )

        # Callbacks
        checkpoint_callback = CheckpointCallback(
            save_freq=checkpoint_freq // self.num_envs,
            save_path=output_dir,
            name_prefix="ppo_grasp"
        )

        eval_callback = EvalCallback(
            self.eval_env,
            best_model_save_path=f"{output_dir}/best_model",
            log_path=f"{output_dir}/eval",
            eval_freq=10_000 // self.num_envs,
            deterministic=True,
            render=False
        )

        callbacks = [checkpoint_callback, eval_callback]

        if self.use_wandb:
            wandb_callback = WandbCallback(
                model_save_path=f"{output_dir}/wandb_models",
                verbose=2
            )
            callbacks.append(wandb_callback)

        # Train
        logger.info("Starting PPO training for grasping...")
        model.learn(
            total_timesteps=total_timesteps,
            callback=callbacks,
            progress_bar=True
        )

        # Save final model
        model.save(f"{output_dir}/final_model")
        logger.info(f"Training complete. Model saved to {output_dir}")

        if self.use_wandb:
            run.finish()

        return model

    def evaluate(self, model_path: str, num_episodes: int = 100):
        """Evaluate trained policy"""
        model = PPO.load(model_path)

        successes = 0
        total_rewards = []

        for episode in range(num_episodes):
            obs, _ = self.eval_env.reset()
            done = False
            episode_reward = 0

            while not done:
                action, _ = model.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, info = self.eval_env.step(action)
                episode_reward += reward
                done = terminated or truncated

                if terminated:
                    successes += 1

            total_rewards.append(episode_reward)

        success_rate = successes / num_episodes
        mean_reward = np.mean(total_rewards)

        logger.info(f"Evaluation: Success Rate = {success_rate:.2%}, Mean Reward = {mean_reward:.2f}")

        return {"success_rate": success_rate, "mean_reward": mean_reward}


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train grasping policy with PPO")
    parser.add_argument("--timesteps", type=int, default=500_000, help="Total timesteps")
    parser.add_argument("--num-envs", type=int, default=4, help="Number of parallel envs")
    parser.add_argument("--no-wandb", action="store_true", help="Disable W&B logging")
    parser.add_argument("--output", default="./rl_checkpoints/grasping", help="Output dir")

    args = parser.parse_args()

    # Train
    trainer = GraspingTrainer(num_envs=args.num_envs, use_wandb=not args.no_wandb)
    model = trainer.train(
        total_timesteps=args.timesteps,
        output_dir=args.output
    )

    # Evaluate
    trainer.evaluate(f"{args.output}/final_model.zip")
