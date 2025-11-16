"""
Mamba-2 State Space Model Architecture
Efficient sequence modeling with linear complexity for long-context processing
Reference: https://arxiv.org/abs/2405.21060
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple
import math
import logging

logger = logging.getLogger(__name__)


class Mamba2Block(nn.Module):
    """
    Mamba-2 Block with Structured State Space Model
    Implements efficient sequence-to-sequence transformation with linear complexity
    """

    def __init__(
        self,
        d_model: int,
        d_state: int = 64,
        d_conv: int = 4,
        expand_factor: int = 2,
        dt_rank: str = "auto",
        conv_bias: bool = True,
        bias: bool = False,
    ):
        """
        Args:
            d_model: Model dimension
            d_state: SSM state dimension
            d_conv: Local convolution width
            expand_factor: Expansion factor for inner dimension
            dt_rank: Rank of delta projection (auto = d_model / 16)
            conv_bias: Whether to use bias in convolution
            bias: Whether to use bias in linear layers
        """
        super().__init__()

        self.d_model = d_model
        self.d_state = d_state
        self.d_conv = d_conv
        self.expand = expand_factor
        self.d_inner = int(self.expand * self.d_model)

        if dt_rank == "auto":
            self.dt_rank = math.ceil(self.d_model / 16)
        else:
            self.dt_rank = dt_rank

        # Input projection (to expand dimension)
        self.in_proj = nn.Linear(d_model, self.d_inner * 2, bias=bias)

        # Depth-wise convolution for local context
        self.conv1d = nn.Conv1d(
            in_channels=self.d_inner,
            out_channels=self.d_inner,
            kernel_size=d_conv,
            groups=self.d_inner,
            padding=d_conv - 1,
            bias=conv_bias,
        )

        # SSM parameters projection
        self.x_proj = nn.Linear(self.d_inner, self.dt_rank + self.d_state * 2, bias=False)

        # Delta (time step) projection
        self.dt_proj = nn.Linear(self.dt_rank, self.d_inner, bias=True)

        # SSM state matrices (A and D)
        # A: State transition matrix (complex-valued for stability)
        A = torch.arange(1, d_state + 1, dtype=torch.float32).repeat(self.d_inner, 1)
        self.A_log = nn.Parameter(torch.log(A))  # Log for stability

        # D: Skip connection parameter
        self.D = nn.Parameter(torch.ones(self.d_inner))

        # Output projection
        self.out_proj = nn.Linear(self.d_inner, d_model, bias=bias)

    def forward(
        self,
        x: torch.Tensor,
        inference_params: Optional[dict] = None,
    ) -> torch.Tensor:
        """
        Forward pass of Mamba-2 block

        Args:
            x: Input tensor (batch, length, d_model)
            inference_params: Optional params for inference caching

        Returns:
            Output tensor (batch, length, d_model)
        """
        batch, seqlen, dim = x.shape

        # Input projection and split
        xz = self.in_proj(x)  # (batch, seqlen, 2 * d_inner)
        x, z = xz.chunk(2, dim=-1)  # Each: (batch, seqlen, d_inner)

        # Convolution for local context
        # Conv1d expects (batch, channels, length)
        x_conv = x.transpose(1, 2)  # (batch, d_inner, seqlen)
        x_conv = self.conv1d(x_conv)[:, :, :seqlen]  # Trim padding
        x_conv = x_conv.transpose(1, 2)  # Back to (batch, seqlen, d_inner)

        # Activation
        x = F.silu(x_conv)

        # SSM computation
        y = self.ssm(x)

        # Gated output
        output = y * F.silu(z)

        # Output projection
        output = self.out_proj(output)

        return output

    def ssm(self, x: torch.Tensor) -> torch.Tensor:
        """
        Structured State Space Model computation

        Args:
            x: Input tensor (batch, length, d_inner)

        Returns:
            Output tensor (batch, length, d_inner)
        """
        batch, seqlen, d_inner = x.shape

        # Project x to get delta, B, C
        x_dbl = self.x_proj(x)  # (batch, seqlen, dt_rank + 2*d_state)

        # Split into delta, B, C
        delta = x_dbl[..., :self.dt_rank]  # (batch, seqlen, dt_rank)
        B = x_dbl[..., self.dt_rank:self.dt_rank + self.d_state]  # (batch, seqlen, d_state)
        C = x_dbl[..., self.dt_rank + self.d_state:]  # (batch, seqlen, d_state)

        # Project delta to d_inner dimension
        delta = self.dt_proj(delta)  # (batch, seqlen, d_inner)

        # Apply softplus for positivity and stability
        delta = F.softplus(delta)

        # Get A matrix
        A = -torch.exp(self.A_log.float())  # (d_inner, d_state)

        # SSM scan (sequential state computation)
        # This is the core of the SSM - can be optimized with parallel scan
        y = self.selective_scan(x, delta, A, B, C, self.D)

        return y

    def selective_scan(
        self,
        x: torch.Tensor,
        delta: torch.Tensor,
        A: torch.Tensor,
        B: torch.Tensor,
        C: torch.Tensor,
        D: torch.Tensor,
    ) -> torch.Tensor:
        """
        Selective scan operation (core of Mamba)
        Implements: h_t = A * h_{t-1} + B * x_t, y_t = C * h_t + D * x_t

        Args:
            x: Input (batch, seqlen, d_inner)
            delta: Time steps (batch, seqlen, d_inner)
            A: State transition (d_inner, d_state)
            B: Input matrix (batch, seqlen, d_state)
            C: Output matrix (batch, seqlen, d_state)
            D: Skip connection (d_inner,)

        Returns:
            Output (batch, seqlen, d_inner)
        """
        batch, seqlen, d_inner = x.shape

        # Discretize continuous parameters
        # A_discrete = exp(delta * A)
        deltaA = torch.exp(delta.unsqueeze(-1) * A)  # (batch, seqlen, d_inner, d_state)

        # B_discrete = delta * B
        deltaB = delta.unsqueeze(-1) * B.unsqueeze(2)  # (batch, seqlen, d_inner, d_state)

        # Initialize state
        h = torch.zeros(batch, d_inner, self.d_state, device=x.device, dtype=x.dtype)

        outputs = []

        # Sequential scan (can be parallelized with associative scan)
        for t in range(seqlen):
            # Update state: h = A * h + B * x
            h = deltaA[:, t] * h + deltaB[:, t] * x[:, t:t+1]

            # Compute output: y = C * h + D * x
            y = torch.einsum('bdn,bn->bd', h, C[:, t]) + D * x[:, t]
            outputs.append(y)

        # Stack outputs
        output = torch.stack(outputs, dim=1)  # (batch, seqlen, d_inner)

        return output


class Mamba2Layer(nn.Module):
    """
    Complete Mamba-2 layer with residual connection and normalization
    """

    def __init__(
        self,
        d_model: int,
        d_state: int = 64,
        d_conv: int = 4,
        expand_factor: int = 2,
        norm_eps: float = 1e-5,
    ):
        super().__init__()

        self.norm = nn.LayerNorm(d_model, eps=norm_eps)
        self.mamba = Mamba2Block(
            d_model=d_model,
            d_state=d_state,
            d_conv=d_conv,
            expand_factor=expand_factor,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward with residual connection

        Args:
            x: Input (batch, length, d_model)

        Returns:
            Output (batch, length, d_model)
        """
        # Pre-norm residual
        output = x + self.mamba(self.norm(x))
        return output


class Mamba2LM(nn.Module):
    """
    Mamba-2 Language Model
    Stack of Mamba-2 layers for efficient sequence modeling
    """

    def __init__(
        self,
        vocab_size: int,
        d_model: int = 768,
        n_layers: int = 12,
        d_state: int = 64,
        d_conv: int = 4,
        expand_factor: int = 2,
        pad_token_id: int = 0,
    ):
        super().__init__()

        self.vocab_size = vocab_size
        self.d_model = d_model
        self.pad_token_id = pad_token_id

        # Token embedding
        self.embedding = nn.Embedding(vocab_size, d_model, padding_idx=pad_token_id)

        # Mamba-2 layers
        self.layers = nn.ModuleList([
            Mamba2Layer(
                d_model=d_model,
                d_state=d_state,
                d_conv=d_conv,
                expand_factor=expand_factor,
            )
            for _ in range(n_layers)
        ])

        # Output normalization
        self.norm_f = nn.LayerNorm(d_model)

        # Language model head
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

        # Tie weights
        self.lm_head.weight = self.embedding.weight

        logger.info(f"Initialized Mamba-2 LM with {n_layers} layers, d_model={d_model}")

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Forward pass

        Args:
            input_ids: Input token IDs (batch, seqlen)
            labels: Optional labels for language modeling loss

        Returns:
            logits: Output logits (batch, seqlen, vocab_size)
            loss: Optional loss if labels provided
        """
        # Embedding
        x = self.embedding(input_ids)  # (batch, seqlen, d_model)

        # Pass through Mamba-2 layers
        for layer in self.layers:
            x = layer(x)

        # Final normalization
        x = self.norm_f(x)

        # Language model head
        logits = self.lm_head(x)

        # Compute loss if labels provided
        loss = None
        if labels is not None:
            # Shift for next-token prediction
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()

            # Flatten
            loss = F.cross_entropy(
                shift_logits.view(-1, self.vocab_size),
                shift_labels.view(-1),
                ignore_index=self.pad_token_id,
            )

        return logits, loss

    def generate(
        self,
        input_ids: torch.Tensor,
        max_length: int = 100,
        temperature: float = 1.0,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> torch.Tensor:
        """
        Generate tokens autoregressively

        Args:
            input_ids: Initial tokens (batch, seqlen)
            max_length: Maximum sequence length
            temperature: Sampling temperature
            top_k: Top-k sampling
            top_p: Nucleus sampling

        Returns:
            Generated tokens (batch, max_length)
        """
        self.eval()
        batch_size = input_ids.shape[0]

        generated = input_ids.clone()

        with torch.no_grad():
            for _ in range(max_length - input_ids.shape[1]):
                # Forward pass
                logits, _ = self.forward(generated)

                # Get next token logits
                next_token_logits = logits[:, -1, :] / temperature

                # Apply top-k filtering
                if top_k is not None:
                    indices_to_remove = next_token_logits < torch.topk(next_token_logits, top_k)[0][..., -1, None]
                    next_token_logits[indices_to_remove] = -float('Inf')

                # Apply top-p (nucleus) filtering
                if top_p is not None:
                    sorted_logits, sorted_indices = torch.sort(next_token_logits, descending=True)
                    cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

                    # Remove tokens with cumulative probability above threshold
                    sorted_indices_to_remove = cumulative_probs > top_p
                    sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                    sorted_indices_to_remove[..., 0] = 0

                    indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
                    next_token_logits[indices_to_remove] = -float('Inf')

                # Sample
                probs = F.softmax(next_token_logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)

                # Append to generated sequence
                generated = torch.cat([generated, next_token], dim=1)

        return generated


# Benchmark and comparison utilities
def compare_efficiency(d_model=512, seqlen=2048, batch=4):
    """
    Compare Mamba-2 vs Transformer efficiency
    """
    import time

    # Create models
    mamba = Mamba2LM(vocab_size=50000, d_model=d_model, n_layers=6)
    mamba.eval()

    # Create transformer for comparison
    transformer_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=8)
    transformer = nn.TransformerEncoder(transformer_layer, num_layers=6)
    transformer.eval()

    # Create input
    x = torch.randint(0, 50000, (batch, seqlen))

    # Benchmark Mamba-2
    with torch.no_grad():
        start = time.time()
        _ = mamba(x)
        mamba_time = time.time() - start

    # Benchmark Transformer
    x_embed = nn.Embedding(50000, d_model)(x)
    with torch.no_grad():
        start = time.time()
        _ = transformer(x_embed.transpose(0, 1))  # Transformer expects (seqlen, batch, d_model)
        transformer_time = time.time() - start

    logger.info(f"\nEfficiency Comparison (seqlen={seqlen}, batch={batch}):")
    logger.info(f"  Mamba-2: {mamba_time:.4f}s")
    logger.info(f"  Transformer: {transformer_time:.4f}s")
    logger.info(f"  Speedup: {transformer_time/mamba_time:.2f}x")

    return mamba_time, transformer_time


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test Mamba-2 model
    model = Mamba2LM(
        vocab_size=50000,
        d_model=512,
        n_layers=6,
        d_state=64,
    )

    # Test forward pass
    batch_size = 2
    seqlen = 128
    input_ids = torch.randint(0, 50000, (batch_size, seqlen))

    logits, _ = model(input_ids)
    print(f"Output shape: {logits.shape}")  # Should be (batch, seqlen, vocab_size)

    # Test generation
    initial = torch.randint(0, 50000, (1, 10))
    generated = model.generate(initial, max_length=50, temperature=0.8, top_k=50)
    print(f"Generated shape: {generated.shape}")

    # Benchmark
    compare_efficiency()
