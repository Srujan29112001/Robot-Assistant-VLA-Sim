# Quick Start Guide

## Prerequisites

- Docker and Docker Compose
- NVIDIA GPU with CUDA support (recommended)
- 16GB+ RAM
- 50GB+ free disk space

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/Robot-Assistant-VLA-Sim.git
cd Robot-Assistant-VLA-Sim
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
- `OPENAI_API_KEY` - for GPT-4 (required for LLM agent)
- `ANTHROPIC_API_KEY` - optional, for Claude
- `HUGGINGFACE_TOKEN` - for downloading models
- `WANDB_API_KEY` - optional, for experiment tracking

### 3. Run setup script

```bash
chmod +x scripts/setup_env.sh
./scripts/setup_env.sh
```

### 4. Start the system

```bash
docker-compose up
```

This will start all services:
- FastAPI backend (port 8000)
- Streamlit dashboard (port 8501)
- Grafana monitoring (port 3000)
- Neo4j browser (port 7474)
- MLflow UI (port 5000)

## First Steps

### 1. Access the Web Dashboard

Open http://localhost:8501 in your browser

### 2. Send your first command

Try these example commands:
- "Navigate to the kitchen"
- "What objects do you see?"
- "Pick up the red bottle"
- "Check battery level"

### 3. Monitor the system

- **Grafana**: http://localhost:3000 (admin/admin)
- **API Docs**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474 (neo4j/robotpassword)

## Running Simulations

### Start Gazebo simulation

```bash
docker-compose --profile simulation up
```

This launches:
- Gazebo with robot model
- ROS2 navigation stack
- SLAM mapping

### Train RL navigation policy

```bash
docker-compose exec api python -m control.rl.train_navigation \
    --algorithm ppo \
    --timesteps 100000
```

## Development

### Run tests

```bash
chmod +x scripts/run_tests.sh
./scripts/run_tests.sh
```

### Build specific service

```bash
docker-compose build api
docker-compose up api
```

### View logs

```bash
docker-compose logs -f api
docker-compose logs -f perception
```

## Troubleshooting

### GPU not detected

Ensure NVIDIA Container Toolkit is installed:
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### Out of memory

Reduce model sizes in `.env`:
```
LLM_MODEL=gpt-3.5-turbo  # Instead of gpt-4
```

### Port conflicts

Change ports in `docker-compose.yml` if 8000, 8501, etc. are in use

## Next Steps

- Read the [Architecture Documentation](docs/architecture.md)
- Explore [API Reference](docs/api.md)
- Try [Advanced Tutorials](docs/tutorials/)
- Join our [Discord Community](https://discord.gg/example)

## Getting Help

- 📖 [Full Documentation](docs/)
- 💬 [GitHub Discussions](https://github.com/yourusername/Robot-Assistant-VLA-Sim/discussions)
- 🐛 [Report Issues](https://github.com/yourusername/Robot-Assistant-VLA-Sim/issues)
