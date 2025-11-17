# Complete Build, Run & Deploy Guide
## Vision-Language Robotic Assistant (VLA-Sim)

This comprehensive guide covers everything you need to build, run, and deploy the Robot Assistant project from scratch.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Building the Project](#building-the-project)
4. [Running Locally](#running-locally)
5. [Running Tests](#running-tests)
6. [Deployment Options](#deployment-options)
7. [Monitoring & Debugging](#monitoring--debugging)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Hardware Requirements

**Minimum (Development/Testing)**
- CPU: 8+ cores
- RAM: 16GB
- Storage: 50GB free
- Optional: NVIDIA GPU with 8GB+ VRAM

**Recommended (Production)**
- CPU: 16+ cores
- RAM: 32GB+
- Storage: 100GB+ SSD
- NVIDIA GPU: RTX 3090 / A5000+ with 24GB VRAM

### Software Requirements

```bash
# Required
- Ubuntu 22.04 LTS (recommended) or similar Linux distro
- Docker 24.0+
- Docker Compose 2.20+
- Git

# Optional but recommended
- NVIDIA Container Toolkit (for GPU support)
- ROS2 Humble (for hardware deployment)
- Python 3.10+ (for local development)
```

### Installing Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### Installing NVIDIA Container Toolkit (for GPU support)

```bash
# Configure repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install toolkit
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Restart Docker
sudo systemctl restart docker

# Test GPU access
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

---

## Initial Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/Robot-Assistant-VLA-Sim.git
cd Robot-Assistant-VLA-Sim
```

### 2. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your preferred editor
nano .env
# or
vim .env
```

**Required API Keys to Add:**

```bash
# AI/LLM Services
OPENAI_API_KEY=sk-...                    # Get from https://platform.openai.com
ANTHROPIC_API_KEY=sk-ant-...             # Get from https://console.anthropic.com
HUGGINGFACE_TOKEN=hf_...                 # Get from https://huggingface.co/settings/tokens

# Optional: Experiment Tracking
WANDB_API_KEY=...                        # Get from https://wandb.ai/authorize

# Security (IMPORTANT: Change in production!)
JWT_SECRET_KEY=change_this_to_random_string_in_production
```

**Database Passwords (Change in production!):**
```bash
POSTGRES_PASSWORD=robot_pass             # Change this!
NEO4J_PASSWORD=robotpassword             # Change this!
```

### 3. Run Setup Script

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Run setup
./scripts/setup_env.sh
```

This will:
- Create necessary directories (`models/`, `data/`, `logs/`)
- Verify Docker installation
- Optionally build Docker images

---

## Building the Project

### Option 1: Build All Services (Recommended First Time)

```bash
# Build all Docker images (takes 10-30 minutes first time)
docker-compose build

# Or build with no cache (forces fresh build)
docker-compose build --no-cache
```

### Option 2: Build Specific Services

```bash
# Build only specific services
docker-compose build api
docker-compose build perception
docker-compose build agent

# Build with parallel jobs (faster)
docker-compose build --parallel
```

### Option 3: Use Automated Build Script

```bash
# Build and start in one command
./scripts/start.sh --build
```

### Verify Build

```bash
# List built images
docker images | grep robot-assistant

# You should see images like:
# robot-assistant-vla-sim-api
# robot-assistant-vla-sim-perception
# robot-assistant-vla-sim-agent
# etc.
```

---

## Running Locally

### Quick Start (All Services)

```bash
# Start all services in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### Using the Start Script (Recommended)

```bash
# Basic start
./scripts/start.sh

# Build and start
./scripts/start.sh --build

# Start with simulation
./scripts/start.sh --build --sim

# Start with hardware (real robot)
./scripts/start.sh --build --robot
```

### Start Services Step-by-Step

```bash
# 1. Start databases first
docker-compose up -d postgres neo4j mongodb redis
echo "Waiting for databases..." && sleep 10

# 2. Start monitoring
docker-compose up -d prometheus grafana node-exporter

# 3. Start MLOps
docker-compose up -d mlflow

# 4. Start core AI services
docker-compose up -d api perception agent

# 5. Start UI
docker-compose up -d streamlit

# 6. (Optional) Start simulation
docker-compose --profile simulation up -d gazebo

# 7. (Optional) Start ROS2 for hardware
docker-compose --profile hardware up -d ros2-core
```

### Access the System

Once running, access these interfaces:

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| **Streamlit Dashboard** | http://localhost:8501 | - |
| **API Documentation** | http://localhost:8000/docs | - |
| **GraphQL Playground** | http://localhost:8000/graphql | - |
| **Grafana Monitoring** | http://localhost:3000 | admin / admin |
| **MLflow Tracking** | http://localhost:5000 | - |
| **Neo4j Browser** | http://localhost:7474 | neo4j / robotpassword |
| **Prometheus Metrics** | http://localhost:9090 | - |

### Verify Services are Running

```bash
# Check all containers
docker-compose ps

# Check API health
curl http://localhost:8000/health

# Should return: {"status":"healthy"}

# Test database connections
docker-compose exec postgres pg_isready
docker-compose exec redis redis-cli ping
docker-compose exec neo4j cypher-shell "RETURN 1" -u neo4j -p robotpassword
```

### Send Your First Command

```bash
# Using curl
curl -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{"query": "What objects do you see?"}'

# Using Python
python3 << EOF
import requests
response = requests.post(
    "http://localhost:8000/command",
    json={"query": "Navigate to the kitchen"}
)
print(response.json())
EOF
```

---

## Running Tests

### Run All Tests

```bash
# Using test script
./scripts/run_tests.sh

# Or manually with Docker
docker-compose exec api pytest tests/ -v

# With coverage report
docker-compose exec api pytest tests/ --cov=. --cov-report=html
```

### Run Specific Test Suites

```bash
# Test perception module
docker-compose exec api pytest tests/test_perception.py -v

# Test API endpoints
docker-compose exec api pytest tests/test_api.py -v

# Test agent/cognition
docker-compose exec api pytest tests/test_agent.py -v

# Test memory/GraphRAG
docker-compose exec api pytest tests/test_memory.py -v
```

### Code Quality Checks

```bash
# Run linting and formatting
docker-compose exec api black . --check
docker-compose exec api flake8 .
docker-compose exec api isort . --check-only
docker-compose exec api mypy .
```

---

## Deployment Options

### Deployment Mode 1: Docker Compose (Development)

**Best for:** Local development, testing, small-scale deployments

```bash
# Development with live code reload
docker-compose up

# Production mode (detached)
docker-compose up -d

# Scale specific services
docker-compose up -d --scale api=3 --scale perception=2

# View logs
docker-compose logs -f api perception

# Stop and remove volumes (WARNING: deletes data!)
docker-compose down -v
```

### Deployment Mode 2: Docker Compose with Simulation

**Best for:** Testing navigation, manipulation, and perception in Gazebo

```bash
# Ensure X11 forwarding is enabled
export DISPLAY=:0
xhost +local:docker

# Start with simulation profile
docker-compose --profile simulation up -d

# Access Gazebo GUI
# The simulation should appear in a window

# Test navigation
curl -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{"query": "Navigate to coordinates (2, 3)"}'
```

### Deployment Mode 3: Docker Compose with Hardware

**Best for:** Deploying to physical robot (TurtleBot3, etc.)

```bash
# Start with hardware profile
docker-compose --profile hardware up -d

# This starts ROS2 nodes for:
# - Navigation (Nav2)
# - SLAM (Cartographer/SLAM Toolbox)
# - Hardware drivers (LiDAR, motors, etc.)
```

### Deployment Mode 4: Kubernetes (Production)

**Best for:** Production, high availability, auto-scaling

#### Prerequisites

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Verify
kubectl version --client

# For local testing, install minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
```

#### Deploy to Kubernetes

```bash
# Apply all manifests
kubectl apply -f k8s/deployment.yaml

# Check deployment status
kubectl get pods -n vla-robot
kubectl get svc -n vla-robot

# Watch pods coming up
kubectl get pods -n vla-robot -w

# Access logs
kubectl logs -f deployment/api -n vla-robot

# Get service URLs (if using LoadBalancer)
kubectl get svc -n vla-robot

# Port forward for local access
kubectl port-forward svc/api 8000:8000 -n vla-robot
```

#### Scale Deployments

```bash
# Scale API service
kubectl scale deployment api --replicas=5 -n vla-robot

# Check Horizontal Pod Autoscaler
kubectl get hpa -n vla-robot

# The HPA will automatically scale based on CPU/memory
```

#### Update Deployments

```bash
# Update image
kubectl set image deployment/api api=your-registry/vla-api:v2.0 -n vla-robot

# Rolling restart
kubectl rollout restart deployment/api -n vla-robot

# Check rollout status
kubectl rollout status deployment/api -n vla-robot
```

### Deployment Mode 5: Production with CI/CD

The project includes GitHub Actions CI/CD pipeline:

```yaml
# .github/workflows/ci.yml runs:
# 1. Code quality checks (black, flake8, isort, mypy)
# 2. Unit tests with pytest
# 3. Docker image builds
# 4. Coverage reporting to Codecov
```

To deploy automatically:

1. Push to `main` branch triggers CI
2. CI builds and tests
3. On success, Docker images are built
4. Tag release to trigger production deployment

---

## Monitoring & Debugging

### View Service Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f perception

# Filter for errors
docker-compose logs -f api | grep ERROR

# Last 100 lines
docker-compose logs --tail=100 api

# Export logs to file
docker-compose logs --no-color > system-logs.txt
```

### Grafana Dashboards

1. Open http://localhost:3000
2. Login with `admin` / `admin`
3. Navigate to **Dashboards** → **Robot Assistant**
4. View real-time metrics:
   - Task completion rates
   - LLM response times
   - Navigation success metrics
   - System resource usage

### Prometheus Metrics

```bash
# View all metrics
curl http://localhost:8000/metrics

# Query Prometheus
open http://localhost:9090

# Example queries:
# - api_request_duration_seconds
# - task_completion_total
# - llm_token_usage_total
```

### MLflow Experiment Tracking

```bash
# View experiments
open http://localhost:5000

# Track training runs
# Metrics are automatically logged when training RL policies or fine-tuning LLMs
```

### Database Inspection

```bash
# PostgreSQL
docker-compose exec postgres psql -U robot robot_db

# Neo4j (Knowledge Graph)
# Open browser: http://localhost:7474
# Or use cypher-shell:
docker-compose exec neo4j cypher-shell -u neo4j -p robotpassword

# MongoDB
docker-compose exec mongodb mongosh robot_telemetry

# Redis
docker-compose exec redis redis-cli
```

### Interactive Debugging

```bash
# Enter container shell
docker-compose exec api /bin/bash

# Inside container:
# - Check file system
# - Run Python scripts
# - Test imports
# - Debug issues

# Run Python REPL with project context
docker-compose exec api python
>>> from perception.vision.object_detection import ViTDINODetector
>>> detector = ViTDINODetector()
```

---

## Troubleshooting

### Issue: Port Already in Use

```bash
# Find process using port
sudo lsof -i :8000
# or
sudo netstat -tulpn | grep :8000

# Kill the process
sudo kill -9 <PID>

# Or change port in .env
echo "API_PORT=8001" >> .env
```

### Issue: GPU Not Detected

```bash
# Verify NVIDIA driver
nvidia-smi

# If not working, install drivers:
ubuntu-drivers devices
sudo ubuntu-drivers autoinstall
sudo reboot

# Test Docker GPU access
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# Check container GPU access
docker-compose exec api nvidia-smi
```

### Issue: Out of Memory

```bash
# Check Docker memory
docker stats

# Increase Docker memory limit
# Docker Desktop → Settings → Resources → Memory: 8GB+

# Or reduce service replicas
docker-compose up -d --scale perception=1 --scale agent=1

# Use smaller LLM model in .env
echo "LLM_MODEL=gpt-3.5-turbo" >> .env
```

### Issue: Services Can't Connect to Databases

```bash
# Check network
docker network ls
docker network inspect robot-assistant-vla-sim_vla-network

# Restart networking
docker-compose down
docker network prune -f
docker-compose up -d

# Wait longer for databases to initialize
# Edit scripts/start.sh and increase sleep time from 10 to 20 seconds
```

### Issue: Docker Build Fails

```bash
# Clean Docker cache
docker system prune -a

# Rebuild with no cache
docker-compose build --no-cache

# Build specific service
docker-compose build --no-cache api

# Check disk space
df -h

# Remove unused images/containers
docker system prune -a --volumes
```

### Issue: Permission Denied Errors

```bash
# Fix ownership of project files
sudo chown -R $USER:$USER .

# Fix script permissions
chmod +x scripts/*.sh

# Docker socket permissions
sudo usermod -aG docker $USER
newgrp docker
```

### Issue: API Returns 500 Errors

```bash
# Check logs for stack trace
docker-compose logs api | tail -100

# Verify environment variables
docker-compose exec api env | grep API_KEY

# Test database connections
docker-compose exec api python -c "
from sqlalchemy import create_engine
import os
engine = create_engine(os.getenv('DATABASE_URL'))
engine.connect()
print('Database connected!')
"

# Restart API service
docker-compose restart api
```

### Issue: Simulation (Gazebo) Won't Start

```bash
# Check X11 forwarding
echo $DISPLAY
xhost +local:docker

# Install X11 dependencies (if needed)
sudo apt-get install x11-xserver-utils

# Test X11
docker run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix ubuntu:22.04 xeyes

# Check Gazebo logs
docker-compose logs gazebo
```

### Debug Mode

```bash
# Enable debug logging
echo "LOG_LEVEL=DEBUG" >> .env

# Restart services
docker-compose restart api perception agent

# View debug logs
docker-compose logs -f api
```

---

## Advanced Usage

### Training Models

#### Train RL Navigation Policy

```bash
docker-compose exec api python control/rl/train_navigation.py \
    --algorithm ppo \
    --timesteps 100000 \
    --env gazebo

# Monitor training in MLflow
open http://localhost:5000
```

#### Fine-tune LLM for Robot Tasks

```bash
docker-compose exec api python cognition/llm/finetune.py \
    --model llama-2-7b \
    --method qlora \
    --epochs 3

# Track experiment in W&B
# Logs automatically uploaded to wandb.ai
```

#### Generate Synthetic Training Data

```bash
docker-compose exec api python simulation/data_generation.py \
    --scenes 1000 \
    --randomize \
    --output data/datasets/synthetic
```

### Database Backups

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U robot robot_db > backup_$(date +%Y%m%d).sql

# Restore PostgreSQL
docker-compose exec -T postgres psql -U robot robot_db < backup_20250117.sql

# Backup Neo4j
docker-compose exec neo4j neo4j-admin database dump neo4j --to-path=/backups

# Backup all data volumes
docker run --rm \
  -v robot-assistant-vla-sim_postgres_data:/data \
  -v $(pwd):/backup \
  ubuntu tar czf /backup/postgres_backup.tar.gz /data
```

### Performance Tuning

```yaml
# Edit docker-compose.yml to adjust resources:
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
          nvidia.com/gpu: '1'
        reservations:
          cpus: '2.0'
          memory: 4G
```

### Security Hardening for Production

```bash
# 1. Change all default passwords in .env
# 2. Generate strong JWT secret
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" >> .env

# 3. Enable HTTPS (use nginx reverse proxy)
# 4. Configure firewall
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# 5. Enable Docker secrets (Swarm mode)
docker swarm init
echo "your_openai_key" | docker secret create openai_key -

# 6. Regular updates
docker-compose pull
docker-compose up -d --force-recreate
```

---

## Quick Reference Commands

```bash
# START
./scripts/start.sh --build           # Build and start all services
./scripts/start.sh --build --sim     # With simulation

# STATUS
docker-compose ps                     # Check running services
curl http://localhost:8000/health     # API health check

# LOGS
docker-compose logs -f api            # Follow API logs
docker-compose logs --tail=100 api    # Last 100 lines

# RESTART
docker-compose restart api            # Restart single service
docker-compose restart                # Restart all

# STOP
docker-compose stop                   # Stop all services
docker-compose down                   # Stop and remove containers
docker-compose down -v                # Stop and remove volumes (data loss!)

# BUILD
docker-compose build                  # Build all
docker-compose build api              # Build specific service

# SCALE
docker-compose up -d --scale api=3    # Scale API to 3 replicas

# EXEC
docker-compose exec api /bin/bash     # Shell into container
docker-compose exec api pytest tests/ # Run tests

# CLEAN
docker system prune -a                # Remove all unused resources
docker volume prune                   # Remove unused volumes
```

---

## Getting Help

- **Documentation**: [docs/](docs/)
- **API Reference**: http://localhost:8000/docs (when running)
- **GitHub Issues**: https://github.com/yourusername/Robot-Assistant-VLA-Sim/issues
- **Discussions**: https://github.com/yourusername/Robot-Assistant-VLA-Sim/discussions

---

## What's Next?

After successfully deploying:

1. **Explore the Streamlit Dashboard**: http://localhost:8501
2. **Read the Architecture Documentation**: [docs/architecture.md](docs/architecture.md)
3. **Try the API Examples**: [docs/api.md](docs/api.md)
4. **Train Your First Model**: [docs/tutorials/](docs/tutorials/)
5. **Contribute**: Read [CONTRIBUTING.md](CONTRIBUTING.md)

---

**System Status**: ✅ Production Ready
**Last Updated**: 2025-01-17

**Built with ❤️ for embodied AI and robotics**
