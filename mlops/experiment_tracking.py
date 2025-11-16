"""
MLOps Integration - MLflow and Weights & Biases
Experiment tracking for model training and evaluation
"""

import mlflow
import mlflow.pytorch
import wandb
from typing import Dict, Any, Optional
import torch
import logging
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class ExperimentTracker:
    """
    Unified experiment tracking with MLflow and W&B
    """

    def __init__(
        self,
        experiment_name: str,
        use_mlflow: bool = True,
        use_wandb: bool = True,
        mlflow_tracking_uri: str = None,
        wandb_project: str = None
    ):
        self.experiment_name = experiment_name
        self.use_mlflow = use_mlflow
        self.use_wandb = use_wandb

        # Initialize MLflow
        if use_mlflow:
            if mlflow_tracking_uri:
                mlflow.set_tracking_uri(mlflow_tracking_uri)
            else:
                mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))

            mlflow.set_experiment(experiment_name)
            logger.info(f"MLflow tracking initialized: {mlflow.get_tracking_uri()}")

        # Initialize W&B
        if use_wandb:
            wandb_project = wandb_project or os.getenv("WANDB_PROJECT", "vla-robot-assistant")
            self.wandb_run = wandb.init(
                project=wandb_project,
                name=experiment_name,
                reinit=True
            )
            logger.info(f"W&B tracking initialized: {wandb_project}")

        self.mlflow_run = None

    def start_run(self, run_name: str = None, tags: Dict[str, str] = None):
        """Start a new tracking run"""
        if self.use_mlflow:
            self.mlflow_run = mlflow.start_run(run_name=run_name, tags=tags)
            logger.info(f"MLflow run started: {self.mlflow_run.info.run_id}")

    def log_params(self, params: Dict[str, Any]):
        """Log hyperparameters"""
        if self.use_mlflow and self.mlflow_run:
            mlflow.log_params(params)

        if self.use_wandb and self.wandb_run:
            wandb.config.update(params)

        logger.debug(f"Logged params: {params}")

    def log_metrics(self, metrics: Dict[str, float], step: int = None):
        """Log metrics"""
        if self.use_mlflow and self.mlflow_run:
            mlflow.log_metrics(metrics, step=step)

        if self.use_wandb and self.wandb_run:
            wandb.log(metrics, step=step)

        logger.debug(f"Logged metrics at step {step}: {metrics}")

    def log_model(
        self,
        model: torch.nn.Module,
        model_name: str,
        artifacts: Dict[str, str] = None
    ):
        """Log trained model"""
        if self.use_mlflow and self.mlflow_run:
            mlflow.pytorch.log_model(model, model_name)

            # Log additional artifacts
            if artifacts:
                for name, path in artifacts.items():
                    mlflow.log_artifact(path, artifact_path=name)

            logger.info(f"Model '{model_name}' logged to MLflow")

        if self.use_wandb and self.wandb_run:
            # Save model to W&B
            model_path = f"./wandb_models/{model_name}.pth"
            Path(model_path).parent.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), model_path)

            wandb.save(model_path)
            logger.info(f"Model '{model_name}' logged to W&B")

    def log_artifact(self, file_path: str, artifact_name: str = None):
        """Log arbitrary artifact"""
        if self.use_mlflow and self.mlflow_run:
            mlflow.log_artifact(file_path, artifact_path=artifact_name)

        if self.use_wandb and self.wandb_run:
            wandb.save(file_path)

        logger.debug(f"Logged artifact: {file_path}")

    def log_image(self, image_name: str, image):
        """Log image (numpy array or PIL Image)"""
        if self.use_wandb and self.wandb_run:
            wandb.log({image_name: wandb.Image(image)})

    def end_run(self):
        """End current tracking run"""
        if self.use_mlflow and self.mlflow_run:
            mlflow.end_run()
            logger.info("MLflow run ended")

        if self.use_wandb and self.wandb_run:
            wandb.finish()
            logger.info("W&B run ended")


class RoboticsExperimentTracker(ExperimentTracker):
    """
    Specialized tracker for robotics experiments
    """

    def log_robot_metrics(
        self,
        episode: int,
        reward: float,
        success: bool,
        steps: int,
        additional_metrics: Dict[str, float] = None
    ):
        """Log robotics-specific metrics"""
        metrics = {
            "episode": episode,
            "reward": reward,
            "success": 1.0 if success else 0.0,
            "steps": steps
        }

        if additional_metrics:
            metrics.update(additional_metrics)

        self.log_metrics(metrics, step=episode)

    def log_navigation_metrics(
        self,
        episode: int,
        distance_traveled: float,
        goal_reached: bool,
        collision: bool,
        time_taken: float
    ):
        """Log navigation-specific metrics"""
        metrics = {
            "nav/distance": distance_traveled,
            "nav/success": 1.0 if goal_reached else 0.0,
            "nav/collision": 1.0 if collision else 0.0,
            "nav/time": time_taken
        }

        self.log_metrics(metrics, step=episode)

    def log_manipulation_metrics(
        self,
        episode: int,
        grasp_success: bool,
        grasp_force: float,
        approach_distance: float
    ):
        """Log manipulation-specific metrics"""
        metrics = {
            "manip/grasp_success": 1.0 if grasp_success else 0.0,
            "manip/force": grasp_force,
            "manip/approach_distance": approach_distance
        }

        self.log_metrics(metrics, step=episode)

    def log_perception_metrics(
        self,
        fps: float,
        detection_accuracy: float,
        num_objects: int
    ):
        """Log perception metrics"""
        metrics = {
            "perception/fps": fps,
            "perception/accuracy": detection_accuracy,
            "perception/num_objects": num_objects
        }

        self.log_metrics(metrics)


# Example usage
if __name__ == "__main__":
    # Initialize tracker
    tracker = RoboticsExperimentTracker(
        experiment_name="rl_navigation_training",
        use_mlflow=True,
        use_wandb=True
    )

    # Start run
    tracker.start_run(
        run_name="ppo_nav_v1",
        tags={"algorithm": "PPO", "environment": "gazebo"}
    )

    # Log hyperparameters
    tracker.log_params({
        "learning_rate": 3e-4,
        "gamma": 0.99,
        "total_timesteps": 1_000_000,
        "policy": "MlpPolicy"
    })

    # Simulate training
    for episode in range(100):
        # Simulate metrics
        reward = 100 - episode * 0.5
        success = episode > 50

        tracker.log_robot_metrics(
            episode=episode,
            reward=reward,
            success=success,
            steps=200
        )

    # Log model (example)
    # model = YourModel()
    # tracker.log_model(model, "final_policy")

    # End run
    tracker.end_run()

    print("Experiment tracking complete!")
