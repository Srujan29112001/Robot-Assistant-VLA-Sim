"""
LLM Fine-tuning with QLoRA (Quantized Low-Rank Adaptation)
Efficient fine-tuning for robotic task planning on consumer GPUs
"""

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType
)
from datasets import load_dataset, Dataset
import logging
from typing import Dict, List
import wandb
import os

logger = logging.getLogger(__name__)


class QLoRAFineTuner:
    """
    Fine-tune LLMs with QLoRA for robotic task planning
    """

    def __init__(
        self,
        model_name: str = "meta-llama/Llama-2-7b-hf",
        use_4bit: bool = True,
        lora_r: int = 64,
        lora_alpha: int = 16,
        lora_dropout: float = 0.1,
    ):
        self.model_name = model_name
        self.use_4bit = use_4bit

        # QLoRA quantization config
        if use_4bit:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16
            )
        else:
            bnb_config = BitsAndBytesConfig(load_in_8bit=True)

        # Load base model
        logger.info(f"Loading base model: {model_name}")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )

        # Prepare for k-bit training
        self.model = prepare_model_for_kbit_training(self.model)

        # LoRA configuration
        lora_config = LoraConfig(
            r=lora_r,
            lora_alpha=lora_alpha,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],  # Llama attention layers
            lora_dropout=lora_dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM
        )

        # Apply LoRA
        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        logger.info("QLoRA model initialized")

    def prepare_robot_dataset(
        self,
        dataset_path: str = None,
        examples: List[Dict] = None
    ) -> Dataset:
        """
        Prepare dataset for robotic task planning

        Format:
        {
            "instruction": "Pick up the red bottle",
            "context": "Objects visible: red bottle, blue cup...",
            "response": "Thought: I need to... Action: Navigate(...)"
        }
        """
        if dataset_path:
            dataset = load_dataset(dataset_path)
        elif examples:
            dataset = Dataset.from_list(examples)
        else:
            # Use default robotic task examples
            dataset = self._create_default_dataset()

        # Format for instruction tuning
        def format_prompt(example):
            prompt = f"""Below is an instruction that describes a robotic task. Write a response that appropriately completes the request.

### Instruction:
{example['instruction']}

### Context:
{example.get('context', 'No additional context')}

### Response:
{example['response']}"""
            return {"text": prompt}

        formatted_dataset = dataset.map(format_prompt)
        return formatted_dataset

    def _create_default_dataset(self) -> Dataset:
        """Create default robotic task dataset"""
        examples = [
            {
                "instruction": "Pick up the red bottle from the left table",
                "context": "Robot sees: red bottle on table, blue cup, book",
                "response": "Thought: I need to navigate to the left table first, then pick up the bottle.\nAction: Navigate(left_table)\nAction: GetPerception()\nAction: PickObject(red_bottle)"
            },
            {
                "instruction": "Where did I last see my keys?",
                "context": "Memory contains: keys on entry table at 10AM",
                "response": "Thought: I should query my memory for the keys.\nAction: QueryMemory('where are the keys')\nFinal Answer: According to my memory, you last saw your keys on the entry table this morning at 10 AM."
            },
            {
                "instruction": "Navigate to the kitchen and find the coffee mug",
                "context": "Current location: living room. Known locations: kitchen, bedroom",
                "response": "Thought: I need to go to the kitchen first.\nAction: Navigate(kitchen)\nAction: ScanEnvironment()\nAction: GetPerception()\nThought: Now I can identify the coffee mug from the perception data."
            },
            {
                "instruction": "Is the robot battery low?",
                "context": "Robot status requested",
                "response": "Thought: I should check my battery level.\nAction: CheckBattery()\nFinal Answer: My battery level is at [X]%."
            },
            {
                "instruction": "Clean up the table",
                "context": "Table has: plates, cups, napkins",
                "response": "Thought: I need to pick up each item and place it properly.\nAction: GetPerception()\nAction: PickObject(plate1)\nAction: Navigate(kitchen)\nAction: PlaceObject(sink)\nThought: Repeat for other items..."
            }
        ]

        return Dataset.from_list(examples)

    def train(
        self,
        dataset: Dataset,
        output_dir: str = "./qlora_checkpoints",
        num_epochs: int = 3,
        batch_size: int = 4,
        learning_rate: float = 2e-4,
        use_wandb: bool = True
    ):
        """
        Train the model with QLoRA

        Args:
            dataset: Training dataset
            output_dir: Where to save checkpoints
            num_epochs: Number of training epochs
            batch_size: Training batch size
            learning_rate: Learning rate
            use_wandb: Whether to use Weights & Biases logging
        """
        # Initialize W&B
        if use_wandb:
            wandb.init(
                project=os.getenv("WANDB_PROJECT", "vla-robot-assistant"),
                name=f"qlora-{self.model_name.split('/')[-1]}",
                config={
                    "model": self.model_name,
                    "lora_r": 64,
                    "learning_rate": learning_rate,
                    "epochs": num_epochs
                }
            )

        # Training arguments
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=4,
            learning_rate=learning_rate,
            fp16=True,
            logging_steps=10,
            save_steps=100,
            save_total_limit=3,
            report_to="wandb" if use_wandb else "none",
            optim="paged_adamw_8bit",  # QLoRA optimizer
            lr_scheduler_type="cosine",
            warmup_steps=100,
        )

        # Trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=dataset,
            tokenizer=self.tokenizer,
        )

        # Train
        logger.info("Starting QLoRA fine-tuning...")
        trainer.train()

        # Save
        self.model.save_pretrained(output_dir + "/final_model")
        self.tokenizer.save_pretrained(output_dir + "/final_model")

        logger.info(f"Model saved to {output_dir}/final_model")

    def generate(self, instruction: str, context: str = "", max_length: int = 512) -> str:
        """
        Generate response for given instruction

        Args:
            instruction: Task instruction
            context: Additional context
            max_length: Max generation length

        Returns:
            Generated response
        """
        prompt = f"""### Instruction:
{instruction}

### Context:
{context}

### Response:
"""

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_length,
                temperature=0.7,
                top_p=0.9,
                do_sample=True,
            )

        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract only the response part
        response = response.split("### Response:")[-1].strip()

        return response


# CLI for training
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fine-tune LLM with QLoRA for robotics")
    parser.add_argument("--model", default="meta-llama/Llama-2-7b-hf", help="Base model")
    parser.add_argument("--output", default="./qlora_checkpoints", help="Output directory")
    parser.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--no-wandb", action="store_true", help="Disable W&B logging")

    args = parser.parse_args()

    # Initialize trainer
    trainer = QLoRAFineTuner(model_name=args.model)

    # Prepare dataset
    dataset = trainer.prepare_robot_dataset()

    # Train
    trainer.train(
        dataset=dataset,
        output_dir=args.output,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        use_wandb=not args.no_wandb
    )

    # Test generation
    print("\n" + "="*50)
    print("Testing generation:")
    print("="*50)

    response = trainer.generate(
        instruction="Pick up the blue cup and bring it to me",
        context="Robot sees: blue cup, red bottle, green book"
    )

    print(f"\nGenerated response:\n{response}")
