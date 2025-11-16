"""
Reinforcement Learning for Robot Navigation
Uses PPO/DQN for learning navigation policies
"""

import gymnasium as gym
import numpy as np
from stable_baselines3 import PPO, DQN
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
import logging
import argparse
import os

logger = logging.getLogger(__name__)


class RobotNavigationEnv(gym.Env):
    """
    Custom Gym environment for robot navigation
    In production, this would interface with Gazebo/ROS2
    """

    def __init__(self, config: dict = None):
        super(RobotNavigationEnv, self).__init__()

        self.config = config or {}
        self.max_steps = self.config.get('max_steps', 500)

        # Define action space: [linear_vel, angular_vel]
        self.action_space = gym.spaces.Box(
            low=np.array([-0.5, -1.0]),
            high=np.array([0.5, 1.0]),
            dtype=np.float32
        )

        # Define observation space: [lidar_scan (10 rays), goal_position (2), robot_velocity (2)]
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(14,),
            dtype=np.float32
        )

        # Internal state
        self.robot_pos = np.array([0.0, 0.0])
        self.goal_pos = np.array([5.0, 5.0])
        self.robot_vel = np.array([0.0, 0.0])
        self.steps = 0

    def reset(self, seed=None, options=None):
        """Reset environment"""
        super().reset(seed=seed)

        # Random start and goal
        self.robot_pos = np.random.uniform(-2, 2, size=2)
        self.goal_pos = np.random.uniform(3, 7, size=2)
        self.robot_vel = np.array([0.0, 0.0])
        self.steps = 0

        obs = self._get_observation()
        return obs, {}

    def step(self, action):
        """Execute action"""
        self.steps += 1

        # Update robot position (simplified dynamics)
        linear_vel, angular_vel = action
        self.robot_vel = action

        # Simple motion model
        self.robot_pos[0] += linear_vel * 0.1
        self.robot_pos[1] += angular_vel * 0.1

        # Get observation
        obs = self._get_observation()

        # Calculate reward
        distance_to_goal = np.linalg.norm(self.goal_pos - self.robot_pos)
        reward = -distance_to_goal * 0.1  # Penalty for being far from goal

        # Check if goal reached
        done = False
        if distance_to_goal < 0.5:
            reward += 100.0  # Large reward for reaching goal
            done = True

        # Check if max steps reached
        if self.steps >= self.max_steps:
            done = True

        # Check collision (simplified)
        if np.any(np.abs(self.robot_pos) > 10):
            reward -= 50.0  # Penalty for leaving bounds
            done = True

        truncated = self.steps >= self.max_steps

        return obs, reward, done, truncated, {}

    def _get_observation(self):
        """Get current observation"""
        # Simplified LiDAR (10 rays)
        lidar = np.random.uniform(0.1, 10.0, size=10)  # Mock data

        # Goal position relative to robot
        relative_goal = self.goal_pos - self.robot_pos

        # Combine observations
        obs = np.concatenate([
            lidar,
            relative_goal,
            self.robot_vel
        ])

        return obs.astype(np.float32)


def train_navigation_policy(
    algorithm: str = 'ppo',
    total_timesteps: int = 100000,
    save_dir: str = './models/rl'
):
    """
    Train navigation policy

    Args:
        algorithm: 'ppo' or 'dqn'
        total_timesteps: Training timesteps
        save_dir: Directory to save models
    """
    logger.info(f"Training navigation policy with {algorithm.upper()}")

    # Create environment
    env = DummyVecEnv([lambda: RobotNavigationEnv()])

    # Callbacks
    os.makedirs(save_dir, exist_ok=True)
    checkpoint_callback = CheckpointCallback(
        save_freq=10000,
        save_path=f"{save_dir}/checkpoints",
        name_prefix=f"{algorithm}_navigation"
    )

    eval_callback = EvalCallback(
        env,
        best_model_save_path=f"{save_dir}/best",
        log_path=f"{save_dir}/logs",
        eval_freq=5000,
        deterministic=True,
        render=False
    )

    # Create model
    if algorithm == 'ppo':
        model = PPO(
            "MlpPolicy",
            env,
            verbose=1,
            tensorboard_log=f"{save_dir}/tensorboard",
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=64,
            n_epochs=10,
        )
    elif algorithm == 'dqn':
        model = DQN(
            "MlpPolicy",
            env,
            verbose=1,
            tensorboard_log=f"{save_dir}/tensorboard",
            learning_rate=1e-4,
            buffer_size=50000,
            learning_starts=1000,
            target_update_interval=1000,
        )
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    # Train
    logger.info("Starting training...")
    model.learn(
        total_timesteps=total_timesteps,
        callback=[checkpoint_callback, eval_callback],
        progress_bar=True
    )

    # Save final model
    final_path = f"{save_dir}/{algorithm}_navigation_final"
    model.save(final_path)
    logger.info(f"Training complete! Model saved to {final_path}")

    return model


def test_policy(model_path: str, num_episodes: int = 10):
    """
    Test trained policy

    Args:
        model_path: Path to saved model
        num_episodes: Number of test episodes
    """
    logger.info(f"Testing policy from {model_path}")

    # Load model
    if 'ppo' in model_path:
        model = PPO.load(model_path)
    else:
        model = DQN.load(model_path)

    # Create environment
    env = RobotNavigationEnv()

    # Test episodes
    total_reward = 0
    successes = 0

    for episode in range(num_episodes):
        obs, _ = env.reset()
        done = False
        episode_reward = 0

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, _ = env.step(action)
            episode_reward += reward

            if done or truncated:
                break

        total_reward += episode_reward
        if episode_reward > 50:  # Consider success if high reward
            successes += 1

        logger.info(f"Episode {episode + 1}: Reward = {episode_reward:.2f}")

    avg_reward = total_reward / num_episodes
    success_rate = successes / num_episodes

    logger.info(f"Average Reward: {avg_reward:.2f}")
    logger.info(f"Success Rate: {success_rate:.1%}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('--algorithm', type=str, default='ppo', choices=['ppo', 'dqn'])
    parser.add_argument('--timesteps', type=int, default=100000)
    parser.add_argument('--mode', type=str, default='train', choices=['train', 'test'])
    parser.add_argument('--model-path', type=str, default=None)

    args = parser.parse_args()

    if args.mode == 'train':
        train_navigation_policy(
            algorithm=args.algorithm,
            total_timesteps=args.timesteps
        )
    else:
        if args.model_path:
            test_policy(args.model_path)
        else:
            print("Please provide --model-path for testing")
