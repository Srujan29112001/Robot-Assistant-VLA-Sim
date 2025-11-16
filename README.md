# Vision-Language Robotic Assistant (VLA-Sim)

A sophisticated embodied AI system combining vision-language models, robotic control, and autonomous planning for home service robotics.

## 🎯 Project Overview

This project implements a multi-modal AI agent that can:
- **See** using Vision Transformers (ViT-DINO), depth estimation (MiDaS), and OCR
- **Understand** natural language commands via Large Language Models
- **Remember** using GraphRAG knowledge graphs and vector memory
- **Act** through ROS2 navigation, manipulation, and learned RL policies
- **Learn** from experience with reinforcement learning and continuous adaptation

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
- Docker & Docker Compose
- NVIDIA GPU with CUDA 11.8+
- 16GB+ RAM (32GB recommended)
- Ubuntu 22.04 (recommended)

### Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/Robot-Assistant-VLA-Sim.git
cd Robot-Assistant-VLA-Sim
```

2. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

3. **Build and launch with Docker Compose**
```bash
docker-compose up --build
```

4. **Access the interfaces**
- Web Dashboard: http://localhost:8501
- API Documentation: http://localhost:8000/docs
- Grafana Monitoring: http://localhost:3000
- Gazebo Simulation: localhost:11345

## 🛠️ Development Setup

### Install Python dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Build ROS2 workspace
```bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
```

### Run simulation only
```bash
docker-compose --profile simulation up
```

### Run with hardware
```bash
docker-compose --profile hardware up
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

```bash
# Run all tests
pytest tests/

# Run specific test suite
pytest tests/test_perception.py

# Run with coverage
pytest --cov=. --cov-report=html
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
  title={Vision-Language Robotic Assistant},
  author={Your Name},
  year={2025},
  url={https://github.com/yourusername/Robot-Assistant-VLA-Sim}
}
```

## 🔗 Resources

- [Documentation](docs/)
- [API Reference](docs/api.md)
- [Architecture Details](docs/architecture.md)
- [Tutorials](docs/tutorials/)

## 📧 Contact

For questions or collaboration: your.email@example.com

---

**Built with ❤️ for embodied AI and robotics**
