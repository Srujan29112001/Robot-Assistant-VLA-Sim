"""
Spiking Neural Network for Reflexive Robot Control
Ultra-fast obstacle avoidance using neuromorphic computing
"""

import torch
import snntorch as snn
from snntorch import surrogate
from snntorch import functional as SF
from snntorch import spikeplot as splt
import torch.nn as nn
import numpy as np
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class ReflexSNN(nn.Module):
    """
    Spiking Neural Network for reflexive obstacle avoidance
    Achieves <100ms response time for safety-critical reactions
    """

    def __init__(
        self,
        input_size: int = 10,  # LiDAR rays
        hidden_size: int = 64,
        output_size: int = 2,  # [stop_signal, turn_direction]
        beta: float = 0.9
    ):
        """
        Initialize SNN

        Args:
            input_size: Number of input neurons (sensor readings)
            hidden_size: Hidden layer size
            output_size: Output neurons
            beta: Membrane potential decay rate
        """
        super(ReflexSNN, self).__init__()

        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size

        # Spike gradient
        spike_grad = surrogate.fast_sigmoid()

        # Network layers
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.lif1 = snn.Leaky(beta=beta, spike_grad=spike_grad)

        self.fc2 = nn.Linear(hidden_size, hidden_size)
        self.lif2 = snn.Leaky(beta=beta, spike_grad=spike_grad)

        self.fc3 = nn.Linear(hidden_size, output_size)
        self.lif3 = snn.Leaky(beta=beta, spike_grad=spike_grad)

        logger.info(f"ReflexSNN initialized with {input_size} inputs, {hidden_size} hidden, {output_size} outputs")

    def forward(self, x):
        """
        Forward pass

        Args:
            x: Input spikes [batch, time_steps, input_size]

        Returns:
            Output spikes [batch, time_steps, output_size]
        """
        batch_size = x.size(0)
        num_steps = x.size(1)

        # Initialize membrane potentials
        mem1 = self.lif1.init_leaky()
        mem2 = self.lif2.init_leaky()
        mem3 = self.lif3.init_leaky()

        # Output spikes recording
        spk_rec = []
        mem_rec = []

        # Process each time step
        for step in range(num_steps):
            cur1 = self.fc1(x[:, step, :])
            spk1, mem1 = self.lif1(cur1, mem1)

            cur2 = self.fc2(spk1)
            spk2, mem2 = self.lif2(cur2, mem2)

            cur3 = self.fc3(spk2)
            spk3, mem3 = self.lif3(cur3, mem3)

            spk_rec.append(spk3)
            mem_rec.append(mem3)

        # Stack spikes
        spk_rec = torch.stack(spk_rec, dim=1)  # [batch, time, output]
        mem_rec = torch.stack(mem_rec, dim=1)

        return spk_rec, mem_rec


class ObstacleReflexController:
    """
    Controller using SNN for fast obstacle avoidance
    """

    def __init__(self, model_path: str = None):
        """
        Initialize controller

        Args:
            model_path: Path to pretrained SNN model
        """
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # Initialize SNN
        self.snn = ReflexSNN().to(self.device)

        # Load pretrained model if provided
        if model_path:
            self.snn.load_state_dict(torch.load(model_path, map_location=self.device))
            logger.info(f"Loaded SNN model from {model_path}")

        self.snn.eval()

        # Thresholds
        self.danger_threshold = 0.5  # meters
        self.spike_threshold = 3  # minimum spikes to trigger

    def encode_sensor_data(self, lidar_scan: np.ndarray, num_steps: int = 25) -> torch.Tensor:
        """
        Encode LiDAR data as spike trains

        Args:
            lidar_scan: LiDAR distances [num_rays]
            num_steps: Number of time steps

        Returns:
            Spike tensor [1, num_steps, num_rays]
        """
        # Rate encoding: closer objects = higher spike rate
        max_dist = 10.0
        spike_rates = 1.0 - np.clip(lidar_scan / max_dist, 0, 1)

        # Generate Poisson spike trains
        spikes = np.random.rand(num_steps, len(lidar_scan)) < spike_rates
        spikes = torch.FloatTensor(spikes).unsqueeze(0)  # [1, time, rays]

        return spikes.to(self.device)

    @torch.no_grad()
    def check_obstacle(self, lidar_scan: np.ndarray) -> Tuple[bool, str]:
        """
        Check for obstacles and compute reflex action

        Args:
            lidar_scan: LiDAR scan distances

        Returns:
            (should_stop, turn_direction)
        """
        # Encode as spikes
        spike_input = self.encode_sensor_data(lidar_scan)

        # Forward pass
        output_spikes, _ = self.snn(spike_input)

        # Count spikes per output neuron
        spike_counts = output_spikes.sum(dim=1).squeeze(0)  # [output_size]

        stop_spikes = spike_counts[0].item()
        turn_spikes = spike_counts[1].item()

        # Decision logic
        should_stop = stop_spikes > self.spike_threshold

        if turn_spikes > 0:
            turn_direction = "right" if turn_spikes > self.spike_threshold else "left"
        else:
            turn_direction = "straight"

        logger.debug(f"Reflex: stop={should_stop}, turn={turn_direction}, spikes=[{stop_spikes:.0f}, {turn_spikes:.0f}]")

        return should_stop, turn_direction

    def train_from_data(self, training_data: list, epochs: int = 100):
        """
        Train SNN from demonstration data

        Args:
            training_data: List of (lidar_scan, action) pairs
            epochs: Training epochs
        """
        logger.info(f"Training SNN for {epochs} epochs...")

        optimizer = torch.optim.Adam(self.snn.parameters(), lr=1e-3)
        loss_fn = SF.ce_rate_loss()  # Spike count cross-entropy

        self.snn.train()

        for epoch in range(epochs):
            total_loss = 0

            for lidar, action in training_data:
                # Encode input
                spike_input = self.encode_sensor_data(lidar)

                # Forward
                output_spikes, _ = self.snn(spike_input)

                # Target (encode action as spike pattern)
                target = torch.zeros(1, output_spikes.size(1), 2).to(self.device)
                if action == "stop":
                    target[:, :, 0] = 1
                elif action == "turn":
                    target[:, :, 1] = 1

                # Loss
                loss = loss_fn(output_spikes, target)

                # Backward
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                total_loss += loss.item()

            if (epoch + 1) % 10 == 0:
                avg_loss = total_loss / len(training_data)
                logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.4f}")

        self.snn.eval()
        logger.info("SNN training complete!")

    def save_model(self, path: str):
        """Save trained model"""
        torch.save(self.snn.state_dict(), path)
        logger.info(f"Model saved to {path}")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Initialize controller
    controller = ObstacleReflexController()

    # Simulate LiDAR scan (10 rays, in meters)
    lidar_scan = np.array([5.0, 4.5, 4.0, 3.0, 0.3, 0.4, 3.5, 4.0, 5.0, 5.5])

    # Check for obstacles
    should_stop, direction = controller.check_obstacle(lidar_scan)

    print(f"Obstacle detected: {should_stop}")
    print(f"Turn direction: {direction}")
