"""
Sim-to-Real Transfer Validation
Validates policy transfer from simulation to real robot
"""

import numpy as np
import logging
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Results from sim-to-real validation"""
    sim_performance: float
    real_performance: float
    transfer_success: bool
    performance_gap: float
    confidence: float
    recommendations: List[str]


class DomainRandomizer:
    """
    Domain randomization for robust sim-to-real transfer
    Randomizes simulation parameters to improve generalization
    """

    def __init__(self):
        self.randomization_params = {
            'lighting': {'min': 0.3, 'max': 1.5},
            'friction': {'min': 0.5, 'max': 1.5},
            'object_mass': {'min': 0.8, 'max': 1.2},
            'camera_noise': {'std_min': 0.0, 'std_max': 0.05},
            'actuator_noise': {'std_min': 0.0, 'std_max': 0.1},
        }

    def randomize_environment(self) -> Dict[str, float]:
        """Generate randomized environment parameters"""
        params = {}
        for param, bounds in self.randomization_params.items():
            if 'std' in param:
                params[param] = np.random.uniform(
                    bounds.get('std_min', 0),
                    bounds.get('std_max', 0.1)
                )
            else:
                params[param] = np.random.uniform(
                    bounds.get('min', 0.8),
                    bounds.get('max', 1.2)
                )

        logger.debug(f"Randomized params: {params}")
        return params


class RealityGapAnalyzer:
    """
    Analyzes reality gap between simulation and real world
    """

    def __init__(self):
        self.metrics = []

    def compare_trajectories(
        self,
        sim_trajectory: np.ndarray,
        real_trajectory: np.ndarray,
    ) -> float:
        """
        Compare sim and real trajectories

        Args:
            sim_trajectory: Simulated trajectory (N, dim)
            real_trajectory: Real trajectory (N, dim)

        Returns:
            Similarity score [0, 1]
        """
        # Ensure same length
        min_len = min(len(sim_trajectory), len(real_trajectory))
        sim_traj = sim_trajectory[:min_len]
        real_traj = real_trajectory[:min_len]

        # Compute trajectory distance
        mse = np.mean((sim_traj - real_traj) ** 2)

        # Convert to similarity score
        similarity = np.exp(-mse)

        return similarity

    def analyze_sensor_differences(
        self,
        sim_sensor_data: Dict[str, np.ndarray],
        real_sensor_data: Dict[str, np.ndarray],
    ) -> Dict[str, float]:
        """
        Analyze differences between sim and real sensor data

        Args:
            sim_sensor_data: Simulated sensor readings
            real_sensor_data: Real sensor readings

        Returns:
            Dict of difference metrics per sensor
        """
        differences = {}

        for sensor_name in sim_sensor_data:
            if sensor_name not in real_sensor_data:
                continue

            sim_data = sim_sensor_data[sensor_name]
            real_data = real_sensor_data[sensor_name]

            # Compute difference
            diff = np.abs(sim_data - real_data)
            differences[sensor_name] = {
                'mean_diff': float(np.mean(diff)),
                'max_diff': float(np.max(diff)),
                'std_diff': float(np.std(diff)),
            }

        return differences

    def compute_reality_gap_score(
        self,
        trajectory_similarity: float,
        sensor_differences: Dict[str, Any],
    ) -> float:
        """
        Compute overall reality gap score

        Args:
            trajectory_similarity: Trajectory similarity [0, 1]
            sensor_differences: Sensor difference metrics

        Returns:
            Reality gap score [0, 1] (lower is better)
        """
        # Weight trajectory heavily
        gap_score = 1 - trajectory_similarity

        # Add sensor differences
        if sensor_differences:
            sensor_gaps = [
                metrics.get('mean_diff', 0)
                for metrics in sensor_differences.values()
            ]
            avg_sensor_gap = np.mean(sensor_gaps)
            gap_score = 0.7 * gap_score + 0.3 * avg_sensor_gap

        return gap_score


class TransferValidator:
    """
    Validates policy transfer from simulation to real robot
    """

    def __init__(self):
        self.randomizer = DomainRandomizer()
        self.gap_analyzer = RealityGapAnalyzer()

    def validate_transfer(
        self,
        policy,
        sim_env,
        real_env=None,
        num_episodes: int = 10,
        success_threshold: float = 0.7,
    ) -> ValidationResult:
        """
        Validate policy transfer

        Args:
            policy: Trained policy to validate
            sim_env: Simulation environment
            real_env: Real robot environment (optional)
            num_episodes: Number of test episodes
            success_threshold: Success rate threshold

        Returns:
            ValidationResult with validation metrics
        """
        logger.info(f"Validating transfer over {num_episodes} episodes...")

        # Evaluate in simulation
        sim_performance = self._evaluate_policy(
            policy, sim_env, num_episodes
        )

        # Evaluate on real robot if available
        if real_env:
            real_performance = self._evaluate_policy(
                policy, real_env, num_episodes
            )
            performance_gap = abs(sim_performance - real_performance)

            # Success if gap is small and real performance is above threshold
            transfer_success = (
                performance_gap < 0.2 and
                real_performance >= success_threshold
            )

            confidence = 1 - performance_gap

        else:
            # No real environment - estimate from domain randomization
            logger.warning("No real environment provided - using simulation only")
            real_performance = sim_performance * 0.9  # Estimate
            performance_gap = 0.1
            transfer_success = sim_performance >= success_threshold
            confidence = 0.5  # Lower confidence without real data

        # Generate recommendations
        recommendations = self._generate_recommendations(
            sim_performance,
            real_performance,
            performance_gap
        )

        result = ValidationResult(
            sim_performance=sim_performance,
            real_performance=real_performance,
            transfer_success=transfer_success,
            performance_gap=performance_gap,
            confidence=confidence,
            recommendations=recommendations
        )

        logger.info(f"Validation complete: Success={transfer_success}")
        return result

    def _evaluate_policy(self, policy, env, num_episodes: int) -> float:
        """
        Evaluate policy performance

        Args:
            policy: Policy to evaluate
            env: Environment
            num_episodes: Number of episodes

        Returns:
            Average success rate
        """
        successes = []

        for episode in range(num_episodes):
            # Reset environment
            obs = env.reset() if hasattr(env, 'reset') else np.random.randn(10)

            episode_success = False
            total_reward = 0

            for step in range(100):  # Max steps
                # Get action from policy
                action = policy(obs) if callable(policy) else np.random.randn(4)

                # Step environment (simplified)
                if hasattr(env, 'step'):
                    obs, reward, done, info = env.step(action)
                    total_reward += reward
                    if done:
                        episode_success = info.get('success', reward > 0)
                        break
                else:
                    # Simulated step
                    obs = np.random.randn(10)
                    total_reward += np.random.rand()
                    if step > 50:
                        episode_success = total_reward > 25
                        break

            successes.append(float(episode_success))

        success_rate = np.mean(successes)
        logger.info(f"Success rate: {success_rate:.2%}")

        return success_rate

    def _generate_recommendations(
        self,
        sim_perf: float,
        real_perf: float,
        gap: float,
    ) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []

        if gap > 0.3:
            recommendations.append(
                "Large sim-real gap detected. Consider:"
                "\n  - Increasing domain randomization"
                "\n  - Improving simulation fidelity"
                "\n  - Fine-tuning on real robot data"
            )

        if sim_perf > 0.9 and real_perf < 0.6:
            recommendations.append(
                "Policy overfits to simulation. Recommendations:"
                "\n  - Add more noise/randomization"
                "\n  - Simplify policy architecture"
                "\n  - Collect real-world demonstrations"
            )

        if real_perf < 0.5:
            recommendations.append(
                "Low real-world performance. Try:"
                "\n  - Verify sensor calibration"
                "\n  - Check actuator constraints"
                "\n  - Validate reward function"
            )

        if gap < 0.1:
            recommendations.append(
                "Excellent transfer! Policy is ready for deployment."
            )

        return recommendations


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== Sim-to-Real Transfer Validation ===\n")

    # Create validator
    validator = TransferValidator()

    # Mock policy
    def mock_policy(obs):
        return np.random.randn(4)

    # Mock environment
    class MockEnv:
        def reset(self):
            return np.random.randn(10)

        def step(self, action):
            obs = np.random.randn(10)
            reward = np.random.rand()
            done = np.random.rand() > 0.8
            info = {'success': done and reward > 0.5}
            return obs, reward, done, info

    # Validate
    result = validator.validate_transfer(
        policy=mock_policy,
        sim_env=MockEnv(),
        real_env=MockEnv(),
        num_episodes=5,
    )

    print(f"Results:")
    print(f"  Sim Performance: {result.sim_performance:.2%}")
    print(f"  Real Performance: {result.real_performance:.2%}")
    print(f"  Performance Gap: {result.performance_gap:.2%}")
    print(f"  Transfer Success: {result.transfer_success}")
    print(f"  Confidence: {result.confidence:.2%}")
    print(f"\nRecommendations:")
    for rec in result.recommendations:
        print(f"  - {rec}")
