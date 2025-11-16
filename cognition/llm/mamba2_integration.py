"""
Mamba-2 Integration for Robot Assistant
Hybrid Mamba-2 + Transformer for efficient long-context processing
"""

import torch
import torch.nn as nn
from transformers import AutoTokenizer, PreTrainedModel
from typing import Optional, Dict, List, Any
import logging
from pathlib import Path

from .mamba2_model import Mamba2LM, Mamba2Layer

logger = logging.getLogger(__name__)


class HybridMamba2Transformer(nn.Module):
    """
    Hybrid model combining Mamba-2 SSM layers with Transformer attention
    - Mamba-2 for efficient long-range processing
    - Transformer for complex reasoning
    """

    def __init__(
        self,
        vocab_size: int,
        d_model: int = 768,
        n_mamba_layers: int = 8,
        n_transformer_layers: int = 4,
        d_state: int = 64,
        nhead: int = 12,
        dim_feedforward: int = 3072,
        pad_token_id: int = 0,
    ):
        super().__init__()

        self.vocab_size = vocab_size
        self.d_model = d_model
        self.pad_token_id = pad_token_id

        # Token embedding
        self.embedding = nn.Embedding(vocab_size, d_model, padding_idx=pad_token_id)

        # Mamba-2 layers (for efficient context processing)
        self.mamba_layers = nn.ModuleList([
            Mamba2Layer(d_model=d_model, d_state=d_state)
            for _ in range(n_mamba_layers)
        ])

        # Transformer layers (for complex reasoning)
        self.transformer_layers = nn.ModuleList([
            nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_feedforward,
                batch_first=True,
                norm_first=True,
            )
            for _ in range(n_transformer_layers)
        ])

        # Output normalization
        self.norm_f = nn.LayerNorm(d_model)

        # Language model head
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)
        self.lm_head.weight = self.embedding.weight  # Tie weights

        logger.info(
            f"Initialized Hybrid Mamba-2 + Transformer "
            f"({n_mamba_layers} Mamba + {n_transformer_layers} Transformer layers)"
        )

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
    ):
        """
        Forward pass through hybrid model

        Args:
            input_ids: Input token IDs (batch, seqlen)
            attention_mask: Optional attention mask
            labels: Optional labels for loss

        Returns:
            logits and optional loss
        """
        # Embedding
        x = self.embedding(input_ids)

        # Pass through Mamba-2 layers (linear complexity)
        for mamba_layer in self.mamba_layers:
            x = mamba_layer(x)

        # Pass through Transformer layers (for complex reasoning)
        # Create attention mask for padding
        if attention_mask is None:
            attention_mask = (input_ids != self.pad_token_id).float()

        # Transformer expects mask of shape (batch, seqlen) with True for tokens to IGNORE
        transformer_mask = ~attention_mask.bool()

        for transformer_layer in self.transformer_layers:
            x = transformer_layer(x, src_key_padding_mask=transformer_mask)

        # Final normalization
        x = self.norm_f(x)

        # Language model head
        logits = self.lm_head(x)

        # Compute loss if labels provided
        loss = None
        if labels is not None:
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            loss = nn.functional.cross_entropy(
                shift_logits.view(-1, self.vocab_size),
                shift_labels.view(-1),
                ignore_index=self.pad_token_id,
            )

        return {"logits": logits, "loss": loss}


class Mamba2RobotLLM:
    """
    Mamba-2 based LLM for robot task planning
    Efficient processing of long context (sensor data, memory, etc.)
    """

    def __init__(
        self,
        model_name_or_path: str = "gpt2",  # Base tokenizer
        use_hybrid: bool = True,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        max_length: int = 4096,  # Mamba-2 can handle long contexts efficiently
    ):
        """
        Initialize Mamba-2 LLM for robot control

        Args:
            model_name_or_path: Base model for tokenizer
            use_hybrid: Use hybrid Mamba-2 + Transformer (better for reasoning)
            device: Device to run on
            max_length: Maximum context length
        """
        self.device = device
        self.max_length = max_length

        # Load tokenizer from existing model
        logger.info(f"Loading tokenizer from {model_name_or_path}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Initialize model
        vocab_size = len(self.tokenizer)
        if use_hybrid:
            self.model = HybridMamba2Transformer(
                vocab_size=vocab_size,
                d_model=768,
                n_mamba_layers=8,
                n_transformer_layers=4,
                pad_token_id=self.tokenizer.pad_token_id,
            ).to(device)
            logger.info("Using Hybrid Mamba-2 + Transformer model")
        else:
            self.model = Mamba2LM(
                vocab_size=vocab_size,
                d_model=768,
                n_layers=12,
                pad_token_id=self.tokenizer.pad_token_id,
            ).to(device)
            logger.info("Using Pure Mamba-2 model")

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 100,
        temperature: float = 0.7,
        top_k: int = 50,
        top_p: float = 0.95,
        **kwargs
    ) -> str:
        """
        Generate text from prompt

        Args:
            prompt: Input prompt
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k: Top-k sampling
            top_p: Nucleus sampling

        Returns:
            Generated text
        """
        # Tokenize
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            max_length=self.max_length,
            truncation=True,
        ).to(self.device)

        input_ids = inputs["input_ids"]

        # Generate
        self.model.eval()
        with torch.no_grad():
            if hasattr(self.model, 'generate'):
                # Use model's generate method
                output_ids = self.model.generate(
                    input_ids,
                    max_length=input_ids.shape[1] + max_new_tokens,
                    temperature=temperature,
                    top_k=top_k,
                    top_p=top_p,
                )
            else:
                # Manual generation for hybrid model
                output_ids = self._generate_hybrid(
                    input_ids,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_k=top_k,
                    top_p=top_p,
                )

        # Decode
        generated_text = self.tokenizer.decode(
            output_ids[0],
            skip_special_tokens=True
        )

        return generated_text

    def _generate_hybrid(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int,
        temperature: float,
        top_k: int,
        top_p: float,
    ) -> torch.Tensor:
        """Generate for hybrid model"""
        generated = input_ids.clone()

        for _ in range(max_new_tokens):
            # Forward pass
            outputs = self.model(generated)
            logits = outputs["logits"]

            # Get next token logits
            next_token_logits = logits[:, -1, :] / temperature

            # Top-k filtering
            if top_k > 0:
                indices_to_remove = next_token_logits < torch.topk(next_token_logits, top_k)[0][..., -1, None]
                next_token_logits[indices_to_remove] = -float('Inf')

            # Top-p filtering
            if top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(next_token_logits, descending=True)
                cumulative_probs = torch.cumsum(nn.functional.softmax(sorted_logits, dim=-1), dim=-1)

                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = 0

                indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
                next_token_logits[indices_to_remove] = -float('Inf')

            # Sample
            probs = nn.functional.softmax(next_token_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Append
            generated = torch.cat([generated, next_token], dim=1)

            # Stop if EOS
            if next_token.item() == self.tokenizer.eos_token_id:
                break

        return generated

    def process_robot_context(
        self,
        sensor_data: Dict[str, Any],
        memory: List[str],
        instruction: str,
    ) -> str:
        """
        Process robot context efficiently with Mamba-2

        Args:
            sensor_data: Current sensor readings
            memory: Relevant memory entries
            instruction: User instruction

        Returns:
            Generated plan/response
        """
        # Build context (Mamba-2 handles long contexts efficiently)
        context_parts = []

        # Add memory (can be very long)
        if memory:
            context_parts.append("## Relevant Memory:\n" + "\n".join(memory))

        # Add sensor data
        context_parts.append(f"## Current Sensors:\n{sensor_data}")

        # Add instruction
        context_parts.append(f"## Instruction:\n{instruction}")

        # Add robot planning prompt
        context_parts.append(
            "\n## Task Plan:\n"
            "Generate a step-by-step plan to accomplish the instruction safely:\n"
        )

        full_prompt = "\n\n".join(context_parts)

        # Generate (Mamba-2 is efficient even with long context)
        plan = self.generate(
            full_prompt,
            max_new_tokens=200,
            temperature=0.7,
        )

        # Extract just the plan
        if "## Task Plan:" in plan:
            plan = plan.split("## Task Plan:")[-1].strip()

        return plan

    def save_pretrained(self, save_path: str):
        """Save model and tokenizer"""
        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)

        # Save model
        torch.save(self.model.state_dict(), save_path / "model.pt")

        # Save tokenizer
        self.tokenizer.save_pretrained(save_path)

        logger.info(f"Model saved to {save_path}")

    def load_pretrained(self, load_path: str):
        """Load pretrained model"""
        load_path = Path(load_path)

        # Load model state
        state_dict = torch.load(load_path / "model.pt", map_location=self.device)
        self.model.load_state_dict(state_dict)

        logger.info(f"Model loaded from {load_path}")


# Convenience function for robot assistant integration
def create_mamba2_robot_llm(
    model_type: str = "hybrid",  # "hybrid" or "pure"
    device: str = "auto",
) -> Mamba2RobotLLM:
    """
    Create Mamba-2 LLM for robot assistant

    Args:
        model_type: "hybrid" (Mamba+Transformer) or "pure" (Mamba only)
        device: Device to use

    Returns:
        Initialized Mamba-2 LLM
    """
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    use_hybrid = (model_type == "hybrid")

    llm = Mamba2RobotLLM(
        model_name_or_path="gpt2",  # For tokenizer
        use_hybrid=use_hybrid,
        device=device,
        max_length=4096,  # Long context support
    )

    logger.info(f"Created Mamba-2 Robot LLM (type={model_type}, device={device})")

    return llm


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test Mamba-2 Robot LLM
    llm = create_mamba2_robot_llm(model_type="hybrid")

    # Test generation
    prompt = "The robot needs to pick up a red bottle from the table. Plan:"
    response = llm.generate(prompt, max_new_tokens=100)
    print(f"\nPrompt: {prompt}")
    print(f"Response: {response}")

    # Test robot context processing
    sensor_data = {
        "camera": "red bottle detected at (1.5m, 0.3m, 0.8m)",
        "lidar": "clear path to table",
        "gripper": "empty"
    }

    memory = [
        "Previously picked bottle from table successfully",
        "Table is located in kitchen",
        "Red bottles are usually fragile"
    ]

    instruction = "Pick up the red bottle and bring it to me"

    plan = llm.process_robot_context(sensor_data, memory, instruction)
    print(f"\nGenerated Plan:\n{plan}")
