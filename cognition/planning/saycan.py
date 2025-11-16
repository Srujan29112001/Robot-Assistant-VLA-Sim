"""
SayCan: Grounding Language in Robotic Affordances
Combines LLM reasoning with learned affordance functions
Reference: Google's "Do As I Can, Not As I Say"
"""

import torch
import torch.nn as nn
from typing import List, Dict, Any, Tuple, Optional
import logging
import numpy as np

logger = logging.getLogger(__name__)


class AffordanceFunction(nn.Module):
    """
    Learned affordance function: how likely can the robot execute an action?
    Trained via RL or behavior cloning
    """

    def __init__(
        self,
        state_dim: int = 128,
        action_dim: int = 32,
        hidden_dim: int = 256,
    ):
        super().__init__()

        self.network = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid()  # Probability [0, 1]
        )

    def forward(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """
        Compute affordance: P(success | state, action)

        Args:
            state: Current state representation
            action: Action embedding

        Returns:
            Affordance score [0, 1]
        """
        combined = torch.cat([state, action], dim=-1)
        return self.network(combined)


class SayCanPlanner:
    """
    SayCan Planner combining LLM and affordances
    """

    def __init__(
        self,
        llm_model: Any,  # Language model for task decomposition
        affordance_model: Optional[AffordanceFunction] = None,
        action_library: Optional[Dict[str, Any]] = None,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
    ):
        """
        Initialize SayCan planner

        Args:
            llm_model: Language model for generating action sequences
            affordance_model: Learned affordance function
            action_library: Available robot actions with embeddings
            device: Compute device
        """
        self.llm = llm_model
        self.affordance_model = affordance_model
        self.device = device

        # Default action library if none provided
        self.action_library = action_library or self._default_action_library()

        # Action embeddings (could be learned or from language model)
        self.action_embeddings = self._create_action_embeddings()

        logger.info(f"Initialized SayCan planner with {len(self.action_library)} actions")

    def _default_action_library(self) -> Dict[str, Dict[str, Any]]:
        """Default robot action library"""
        return {
            "pick_object": {
                "description": "Pick up an object from a surface",
                "parameters": ["object_name", "location"],
                "preconditions": ["gripper_empty", "object_visible"],
            },
            "place_object": {
                "description": "Place held object at location",
                "parameters": ["location"],
                "preconditions": ["gripper_holding_object"],
            },
            "navigate_to": {
                "description": "Navigate to a location",
                "parameters": ["location"],
                "preconditions": ["path_clear"],
            },
            "open_container": {
                "description": "Open a container (drawer, door, etc.)",
                "parameters": ["container_name"],
                "preconditions": ["near_container"],
            },
            "close_container": {
                "description": "Close a container",
                "parameters": ["container_name"],
                "preconditions": ["near_container", "container_open"],
            },
            "scan_environment": {
                "description": "Look around and update world model",
                "parameters": [],
                "preconditions": [],
            },
        }

    def _create_action_embeddings(self) -> Dict[str, torch.Tensor]:
        """Create embeddings for each action (simplified)"""
        embeddings = {}
        for action_name in self.action_library:
            # In practice, use LLM to embed action descriptions
            # Here: random embeddings for demonstration
            embeddings[action_name] = torch.randn(32, device=self.device)

        return embeddings

    def plan(
        self,
        instruction: str,
        current_state: Dict[str, Any],
        max_steps: int = 10,
        temperature: float = 0.7,
        affordance_weight: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Generate action plan using SayCan

        Args:
            instruction: Natural language instruction
            current_state: Current robot state
            max_steps: Maximum planning steps
            temperature: LLM sampling temperature
            affordance_weight: Weight for affordance scores (0-1)

        Returns:
            List of selected actions with scores
        """
        plan = []
        state = current_state.copy()

        # Encode current state
        state_embedding = self._encode_state(state)

        for step in range(max_steps):
            # Get action proposals from LLM
            action_proposals = self._llm_propose_actions(
                instruction,
                plan,
                state,
                temperature=temperature
            )

            if not action_proposals:
                logger.info("No more actions proposed by LLM")
                break

            # Score actions with SayCan formula
            scored_actions = self._score_actions(
                action_proposals,
                state_embedding,
                affordance_weight
            )

            # Select best action
            if not scored_actions:
                logger.warning("No valid actions available")
                break

            best_action = scored_actions[0]

            # Check if task is complete
            if self._is_task_complete(best_action, instruction):
                logger.info("Task complete")
                break

            # Add to plan
            plan.append(best_action)

            # Update state (simplified - in practice, execute and observe)
            state = self._update_state(state, best_action)
            state_embedding = self._encode_state(state)

            logger.info(f"Step {step + 1}: {best_action['action']} (score: {best_action['score']:.3f})")

        return plan

    def _llm_propose_actions(
        self,
        instruction: str,
        current_plan: List[Dict],
        state: Dict[str, Any],
        temperature: float,
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to propose next actions

        Args:
            instruction: Original instruction
            current_plan: Actions taken so far
            state: Current state
            temperature: Sampling temperature

        Returns:
            List of proposed actions with LLM scores
        """
        # Build prompt
        prompt = self._build_llm_prompt(instruction, current_plan, state)

        # Get LLM completion (simplified - actual implementation would use the LLM)
        # For demonstration, return some plausible actions
        if not current_plan:
            # Initial actions
            proposals = [
                {"action": "scan_environment", "llm_score": 0.8, "parameters": {}},
                {"action": "navigate_to", "llm_score": 0.9, "parameters": {"location": "kitchen"}},
            ]
        elif len(current_plan) == 1:
            proposals = [
                {"action": "pick_object", "llm_score": 0.95, "parameters": {"object_name": "bottle", "location": "table"}},
                {"action": "scan_environment", "llm_score": 0.4, "parameters": {}},
            ]
        else:
            proposals = [
                {"action": "place_object", "llm_score": 0.9, "parameters": {"location": "counter"}},
            ]

        return proposals

    def _score_actions(
        self,
        proposals: List[Dict[str, Any]],
        state_embedding: torch.Tensor,
        affordance_weight: float,
    ) -> List[Dict[str, Any]]:
        """
        Score actions using SayCan formula:
        score = LLM_prob^(1-w) * Affordance^w

        Args:
            proposals: Actions proposed by LLM
            state_embedding: Current state embedding
            affordance_weight: Weight for affordance

        Returns:
            Sorted list of scored actions
        """
        scored = []

        for proposal in proposals:
            action_name = proposal["action"]

            # Get action embedding
            if action_name not in self.action_embeddings:
                logger.warning(f"Unknown action: {action_name}")
                continue

            action_embedding = self.action_embeddings[action_name]

            # Compute affordance
            if self.affordance_model is not None:
                with torch.no_grad():
                    affordance = self.affordance_model(
                        state_embedding.unsqueeze(0),
                        action_embedding.unsqueeze(0)
                    ).item()
            else:
                # Default: assume moderate affordance
                affordance = 0.7

            # SayCan score
            llm_score = proposal.get("llm_score", 0.5)
            saycan_score = (llm_score ** (1 - affordance_weight)) * (affordance ** affordance_weight)

            scored.append({
                **proposal,
                "affordance": affordance,
                "saycan_score": saycan_score,
                "score": saycan_score,  # Alias for easier access
            })

        # Sort by score
        scored.sort(key=lambda x: x["score"], reverse=True)

        return scored

    def _encode_state(self, state: Dict[str, Any]) -> torch.Tensor:
        """Encode state to embedding (simplified)"""
        # In practice: use perception features, robot joint states, etc.
        # Here: random embedding for demonstration
        return torch.randn(128, device=self.device)

    def _build_llm_prompt(
        self,
        instruction: str,
        plan: List[Dict],
        state: Dict[str, Any],
    ) -> str:
        """Build prompt for LLM"""
        prompt_parts = [
            "You are a helpful robot assistant. Given the task and current state, suggest the next action.",
            f"\nTask: {instruction}",
            f"\nCurrent state: {state}",
        ]

        if plan:
            actions_taken = [f"{i+1}. {a['action']}" for i, a in enumerate(plan)]
            prompt_parts.append(f"\nActions taken:\n" + "\n".join(actions_taken))

        prompt_parts.append(f"\nAvailable actions: {list(self.action_library.keys())}")
        prompt_parts.append("\nNext action:")

        return "\n".join(prompt_parts)

    def _update_state(self, state: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
        """Update state after action (simplified simulation)"""
        new_state = state.copy()

        # Simple state transitions based on action
        action_name = action["action"]

        if action_name == "pick_object":
            new_state["gripper_holding_object"] = True
            new_state["gripper_empty"] = False

        elif action_name == "place_object":
            new_state["gripper_holding_object"] = False
            new_state["gripper_empty"] = True

        elif action_name == "navigate_to":
            new_state["current_location"] = action["parameters"].get("location", "unknown")

        return new_state

    def _is_task_complete(self, action: Dict[str, Any], instruction: str) -> bool:
        """Check if task is likely complete"""
        # Simple heuristic: check if action is terminal (place, close, etc.)
        terminal_actions = ["place_object", "close_container"]
        return action["action"] in terminal_actions


class AffordanceTrainer:
    """Train affordance functions from robot experience"""

    def __init__(
        self,
        affordance_model: AffordanceFunction,
        learning_rate: float = 1e-4,
    ):
        self.model = affordance_model
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        self.criterion = nn.BCELoss()

    def train_step(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        success_labels: torch.Tensor,
    ) -> float:
        """
        Train on batch of (state, action, success) tuples

        Args:
            states: State embeddings (batch, state_dim)
            actions: Action embeddings (batch, action_dim)
            success_labels: Success labels [0, 1] (batch, 1)

        Returns:
            Loss value
        """
        self.optimizer.zero_grad()

        # Forward
        predictions = self.model(states, actions)

        # Loss
        loss = self.criterion(predictions, success_labels)

        # Backward
        loss.backward()
        self.optimizer.step()

        return loss.item()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== Testing SayCan Planner ===")

    # Create simple LLM mock
    class MockLLM:
        def generate(self, prompt):
            return "navigate_to kitchen"

    # Initialize planner
    planner = SayCan Planner(
        llm_model=MockLLM(),
        affordance_model=None,  # Will use default affordances
    )

    # Test planning
    instruction = "Bring me a bottle from the kitchen"
    initial_state = {
        "current_location": "living_room",
        "gripper_empty": True,
        "objects_visible": ["table", "chair"],
    }

    plan = planner.plan(
        instruction=instruction,
        current_state=initial_state,
        max_steps=5,
        affordance_weight=0.5,
    )

    print(f"\nGenerated plan for: '{instruction}'")
    for i, action in enumerate(plan):
        print(f"{i+1}. {action['action']}")
        print(f"   LLM score: {action.get('llm_score', 0):.3f}")
        print(f"   Affordance: {action.get('affordance', 0):.3f}")
        print(f"   SayCan score: {action.get('score', 0):.3f}")

    print("\n=== SayCan test completed ===")
