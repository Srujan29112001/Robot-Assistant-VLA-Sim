# 🤖 Vision-Language Robotic Assistant (VLA-Sim)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![ROS2 Humble](https://img.shields.io/badge/ROS2-Humble-blue.svg)](https://docs.ros.org/en/humble/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

A sophisticated embodied AI system combining vision-language models, robotic control, and autonomous planning for home service robotics.

## 📑 Table of Contents

- [Project Overview](#-project-overview)
- [Architecture](#-architecture)
- [Key Features](#-key-features)
- [Installation](#-installation)
- [Development Setup](#-development-setup)
- [Usage](#-usage)
- [Testing](#-testing)
- [Monitoring](#-monitoring)
- [Training Models](#-training-models)
- [Project Structure](#-project-structure)
- [Contributing](#-contributing)
- [Resources](#-resources)

## 🎯 Project Overview

This project implements a multi-modal AI agent that can:
- 👁️ **See** using Vision Transformers (ViT-DINO), depth estimation (MiDaS), and OCR
- 🧠 **Understand** natural language commands via Large Language Models
- 💾 **Remember** using GraphRAG knowledge graphs and vector memory
- 🤖 **Act** through ROS2 navigation, manipulation, and learned RL policies
- 📈 **Learn** from experience with reinforcement learning and continuous adaptation

### ⚡ Quick Facts

- **100+ Microservices**: Fully containerized with Docker & Kubernetes support
- **Production-Ready**: Includes monitoring (Prometheus/Grafana), MLOps (MLflow), and CI/CD
- **Hardware & Simulation**: Works with real robots (TurtleBot3) and Gazebo simulation
- **Advanced AI**: Integrates GPT-4, Claude, LLaMA, RT-2 VLA, and custom RL policies
- **Enterprise Security**: JWT auth, mTLS, secrets management, and ROS2 security

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface Layer                     │
│           (Streamlit Dashboard, Voice, REST API)            │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────────┐
│                    FastAPI Gateway (MCP)                     │
│              (Authentication, Rate Limiting)                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────┴──────┐ ┌─────┴─────┐ ┌──────┴──────┐
│  Perception  │ │ Cognition │ │   Control   │
│              │ │           │ │             │
│ • ViT-DINO   │ │ • LLM     │ │ • Nav Stack │
│ • MiDaS      │ │ • VLA     │ │ • MoveIt2   │
│ • OCR        │ │ • Agent   │ │ • RL Policy │
│ • VLAD       │ │           │ │ • SNN       │
└──────────────┘ └─────┬─────┘ └─────────────┘
                       │
                ┌──────┴──────┐
                │   Memory    │
                │  • GraphRAG │
                │  • Vector DB│
                └─────────────┘
                       │
        ┌──────────────┴──────────────┐
        │         ROS2 Layer          │
        │  (Middleware & Communication)│
        └──────────────┬──────────────┘
                       │
        ┌──────────────┴──────────────┐
        │      Simulation Layer       │
        │  (Gazebo / NVIDIA Isaac)    │
        └─────────────────────────────┘
```

## 🚀 Key Features

### Vision & Perception
- **ViT-DINO**: Self-supervised object detection and segmentation
- **MiDaS**: Monocular depth estimation for 3D understanding
- **DeepSeek OCR**: Text recognition for reading labels and signs
- **VLAD**: Visual place recognition and object retrieval

### Cognition & Planning
- **LLM Brain**: Fine-tuned language models (with QLoRA) for task planning
- **Vision-Language-Action (VLA)**: Direct image-to-action policies
- **LangChain Agent**: Tool orchestration with ReAct reasoning
- **MCP Protocol**: Standardized AI-to-robot interface

### Memory & Knowledge
- **GraphRAG**: Knowledge graph for spatial and temporal reasoning
- **Vector Database**: Episodic memory with semantic retrieval
- **Long-term Memory**: Persistent storage of experiences and facts

### Control & Execution
- **ROS2 Navigation**: SLAM, path planning, obstacle avoidance
- **MoveIt2**: Motion planning for manipulation
- **Deep RL**: Learned policies for navigation and grasping (Q-learning, PPO)
- **Spiking Neural Networks**: Ultra-fast reflexive behaviors (<100ms)

### Infrastructure
- **Docker & Kubernetes**: Containerized microservices
- **Prometheus & Grafana**: Real-time monitoring and metrics
- **MLflow & W&B**: Experiment tracking and model registry
- **FastAPI**: High-performance REST and GraphQL endpoints

## 📦 Installation

### Prerequisites
- **Docker** 24.0+ & **Docker Compose** 2.20+
- **NVIDIA GPU** with CUDA 11.8+ (optional but recommended)
- **16GB+ RAM** (32GB recommended for production)
- **Ubuntu 22.04** LTS (recommended)

> 📘 **For detailed installation instructions, see [BUILD_RUN_DEPLOY_GUIDE.md](BUILD_RUN_DEPLOY_GUIDE.md)**

### Quick Start (5 minutes)

1. **Clone the repository**
```bash
git clone https://github.com/Srujan29112001/Robot-Assistant-VLA-Sim.git
cd Robot-Assistant-VLA-Sim
```

2. **Set up environment variables**
```bash
cp .env.example .env
nano .env  # Add your API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
```

> ⚠️ **Important**: Update the following in `.env`:
> - Add your API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `HUGGINGFACE_TOKEN`
> - Change default passwords: `POSTGRES_PASSWORD`, `NEO4J_PASSWORD`
> - Generate secure JWT secret: `JWT_SECRET_KEY`

3. **Build and launch with Docker Compose**
```bash
# Start all core services (API, databases, monitoring, UI)
docker-compose up --build -d

# Wait for services to initialize (~30 seconds)
docker-compose logs -f api
```

4. **Access the interfaces**
- 🎨 **Web Dashboard**: http://localhost:8501
- 📚 **API Documentation**: http://localhost:8000/docs
- 📊 **Grafana Monitoring**: http://localhost:3000 (admin/admin)
- 🔍 **GraphQL Playground**: http://localhost:8000/graphql
- 🧪 **MLflow Tracking**: http://localhost:5000

5. **Test the system**
```bash
# Check API health
curl http://localhost:8000/health

# Send a test command
curl -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{"query": "What can you do?"}'
```

## 🛠️ Development Setup

### Local Python Development (Optional)
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install package in editable mode
pip install -e .
```

### Build ROS2 Workspace
```bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
```

### Deployment Profiles

#### Run with Simulation (Gazebo)
```bash
# Enable X11 forwarding for GUI
export DISPLAY=:0
xhost +local:docker

# Start with simulation profile
docker-compose --profile simulation up --build
```

#### Run with Hardware (Real Robot)
```bash
# Start with hardware profile (includes ROS2 drivers)
docker-compose --profile hardware up --build
```

#### Run Core Services Only (Development)
```bash
# Just API, databases, and UI (no ROS2/Gazebo)
docker-compose up api postgres redis neo4j mongodb streamlit grafana
```

## 📚 Usage

### Basic Command Example
```python
import requests

# Send a command to the robot
response = requests.post(
    "http://localhost:8000/command",
    json={"query": "Pick up the red bottle from the left table"}
)
print(response.json())
```

### GraphQL Query
```graphql
mutation {
  planTask(task: "Navigate to the kitchen and find my keys") {
    id
    status
    steps
  }
}
```

### Check robot status
```bash
curl http://localhost:8000/state
```

## 🧪 Testing

### Run Tests in Docker (Recommended)
```bash
# Run all tests
docker-compose exec api pytest tests/ -v

# Run specific test suites
docker-compose exec api pytest tests/test_perception.py -v
docker-compose exec api pytest tests/test_api.py -v
docker-compose exec api pytest tests/test_integration.py -v

# Run with coverage report
docker-compose exec api pytest tests/ --cov=. --cov-report=html --cov-report=term

# View coverage report
open htmlcov/index.html
```

### Run Tests Locally
```bash
# In virtual environment
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with coverage
pytest --cov=. --cov-report=html
```

### Code Quality Checks
```bash
# Linting and formatting
docker-compose exec api black . --check
docker-compose exec api flake8 .
docker-compose exec api isort . --check-only
docker-compose exec api mypy .
```

## 📊 Monitoring

Access Grafana dashboards at http://localhost:3000 to monitor:
- Task completion rates
- LLM response times
- Navigation success metrics
- Sensor data streams
- System resource usage

## 🎓 Training Models

### Train RL Navigation Policy
```bash
python control/rl/train_navigation.py --env gazebo --episodes 10000
```

### Fine-tune LLM for Robot Tasks
```bash
python cognition/llm/finetune.py --model llama-2-7b --method qlora
```

### Generate Synthetic Training Data
```bash
python simulation/data_generation.py --scenes 1000 --randomize
```

## 🏗️ Project Structure

```
Robot-Assistant-VLA-Sim/
├── api/                    # FastAPI backend
│   ├── mcp/               # Model Context Protocol server
│   ├── routes/            # API endpoints
│   └── models/            # Pydantic schemas
├── perception/            # Vision & sensing
│   ├── vision/            # ViT-DINO, object detection
│   ├── depth/             # MiDaS depth estimation
│   └── ocr/               # Text recognition
├── cognition/             # AI reasoning
│   ├── llm/               # Language model integration
│   ├── vla/               # Vision-Language-Action models
│   └── agent/             # LangChain orchestration
├── memory/                # Knowledge & retrieval
│   ├── graphrag/          # Graph-based RAG
│   └── vector_db/         # FAISS/Chroma DB
├── control/               # Robot control
│   ├── navigation/        # Nav2 integration
│   ├── manipulation/      # MoveIt2 integration
│   ├── rl/                # Reinforcement learning
│   └── snn/               # Spiking neural networks
├── simulation/            # Virtual environments
│   ├── gazebo/            # Gazebo worlds
│   └── isaac/             # NVIDIA Isaac Sim
├── ros2_ws/               # ROS2 workspace
│   └── src/               # ROS2 packages
├── monitoring/            # Observability
│   ├── prometheus/        # Metrics collection
│   └── grafana/           # Dashboards
├── ui/                    # User interfaces
│   └── streamlit/         # Web dashboard
├── docker/                # Docker configurations
├── tests/                 # Test suites
├── docs/                  # Documentation
└── config/                # Configuration files
```

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📝 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- **DeepMind RT-2** for Vision-Language-Action models
- **NVIDIA Isaac Sim** for high-fidelity simulation
- **Microsoft GraphRAG** for knowledge graph RAG
- **ROS2** and the open-source robotics community

## 📖 Citation

If you use this project in your research, please cite:

```bibtex
@software{vla_robotic_assistant,
  title={Vision-Language Robotic Assistant (VLA-Sim)},
  author={Srujan Deshpande},
  year={2025},
  url={https://github.com/Srujan29112001/Robot-Assistant-VLA-Sim}
}
```

## 🔗 Resources

- 📘 [Complete Build & Deploy Guide](BUILD_RUN_DEPLOY_GUIDE.md)
- 📚 [Documentation](docs/)
- 🚀 [Deployment Guide](DEPLOYMENT.md)
- 🤝 [Contributing Guidelines](CONTRIBUTING.md)
- ⚙️ [Project Features](FEATURES_COMPLETE.md)

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/Srujan29112001/Robot-Assistant-VLA-Sim/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Srujan29112001/Robot-Assistant-VLA-Sim/discussions)
- **Documentation**: [docs/](docs/)

---

**Built with ❤️ for embodied AI and robotics**

*Star ⭐ this repository if you find it helpful!*
