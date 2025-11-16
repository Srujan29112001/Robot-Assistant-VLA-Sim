# Deployment Guide - Vision-Language Robotic Assistant

Complete deployment instructions for development, testing, and production environments.

## 📋 Prerequisites

### Hardware Requirements

**Minimum (Development/Testing)**
- CPU: 8+ cores
- RAM: 16GB+
- Storage: 50GB+
- Optional: NVIDIA GPU with 8GB+ VRAM

**Recommended (Production)**
- CPU: 16+ cores
- RAM: 32GB+
- Storage: 100GB+ SSD
- NVIDIA GPU: RTX 3090 / A5000+ with 24GB VRAM

### Software Requirements

```bash
- Docker 24.0+
- Docker Compose 2.20+
- NVIDIA Container Toolkit (for GPU)
- Ubuntu 22.04 LTS (recommended)
- ROS2 Humble (for hardware deployment)
```

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/Robot-Assistant-VLA-Sim.git
cd Robot-Assistant-VLA-Sim
```

### 2. Configure Environment

```bash
# Copy example environment
cp .env.example .env

# Edit with your API keys
nano .env
```

**Required API Keys:**
- `OPENAI_API_KEY` - For GPT-4 (get from https://platform.openai.com)
- `ANTHROPIC_API_KEY` - For Claude (get from https://console.anthropic.com)
- `HUGGINGFACE_TOKEN` - For model downloads
- `WANDB_API_KEY` - For experiment tracking (optional)

### 3. Start Services

**Option A: Development Mode (Quick Start)**
```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

**Option B: With Simulation**
```bash
./scripts/start.sh --build --sim
```

**Option C: Manual Docker Compose**
```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# With simulation
docker-compose --profile simulation up -d
```

### 4. Verify Deployment

```bash
# Check service health
curl http://localhost:8000/health

# View logs
docker-compose logs -f api

# Check running containers
docker-compose ps
```

## 🌐 Access Points

Once deployed, access the system at:

| Service | URL | Credentials |
|---------|-----|-------------|
| **API Docs** | http://localhost:8000/docs | N/A |
| **GraphQL** | http://localhost:8000/graphql | N/A |
| **Streamlit UI** | http://localhost:8501 | N/A |
| **Grafana** | http://localhost:3000 | admin / admin |
| **MLflow** | http://localhost:5000 | N/A |
| **Neo4j Browser** | http://localhost:7474 | neo4j / robotpassword |
| **Prometheus** | http://localhost:9090 | N/A |

## 📦 Deployment Modes

### Development Mode

For local development with hot reload:

```bash
# Start with volume mounts for live code changes
docker-compose up -d

# Logs
docker-compose logs -f api perception agent
```

### Simulation Mode

For testing in Gazebo simulation:

```bash
# Requires X11 forwarding
export DISPLAY=:0
xhost +local:docker

# Start with simulation
docker-compose --profile simulation up -d

# Launch Gazebo
docker-compose exec gazebo gazebo --verbose
```

### Production Mode (Kubernetes)

For scalable production deployment:

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/deployment.yaml

# Check pods
kubectl get pods -n vla-robot

# Access via LoadBalancer
kubectl get svc -n vla-robot
```

## 🔧 Configuration

### Scaling Services

Edit `docker-compose.yml` to scale replicas:

```yaml
services:
  api:
    deploy:
      replicas: 3  # Scale API to 3 instances
```

Or use Docker Compose scale:

```bash
docker-compose up -d --scale api=3
```

### GPU Configuration

Ensure NVIDIA runtime is configured:

```bash
# Test GPU access
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# Services with GPU:
# - api
# - perception
# - agent
```

### Resource Limits

Adjust in `docker-compose.yml`:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
          nvidia.com/gpu: '1'
        reservations:
          memory: 2G
          nvidia.com/gpu: '1'
```

## 🧪 Testing Deployment

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Databases
docker-compose exec postgres pg_isready
docker-compose exec redis redis-cli ping
docker-compose exec neo4j cypher-shell "RETURN 1"
```

### Integration Tests

```bash
# Run test suite
docker-compose exec api pytest tests/ -v

# Specific tests
docker-compose exec api pytest tests/test_integration.py -v
```

### Load Testing

```bash
# Install locust
pip install locust

# Run load test
locust -f tests/load_test.py --host=http://localhost:8000
```

## 📊 Monitoring

### Grafana Dashboards

1. Access http://localhost:3000
2. Login with admin/admin
3. Navigate to Dashboards → Robot Assistant
4. View real-time metrics

### Prometheus Metrics

- API metrics: http://localhost:8000/metrics
- System metrics: http://localhost:9100/metrics
- Custom metrics exposed via instrumentator

### Logging

```bash
# Centralized logs
docker-compose logs -f

# Specific service
docker-compose logs -f api

# Follow with grep
docker-compose logs -f api | grep ERROR

# Export logs
docker-compose logs --no-color > logs.txt
```

## 🔐 Security Considerations

### Production Checklist

- [ ] Change default passwords in .env
- [ ] Enable HTTPS/TLS (use nginx reverse proxy)
- [ ] Configure firewall rules
- [ ] Enable JWT authentication
- [ ] Set up secrets management (Vault/AWS Secrets Manager)
- [ ] Enable ROS2 security (DDS encryption)
- [ ] Regular security updates
- [ ] API rate limiting configured
- [ ] Database backups automated

### Secrets Management

```bash
# Using Docker secrets (Swarm mode)
echo "your_api_key" | docker secret create openai_key -

# Using Kubernetes secrets
kubectl create secret generic vla-secrets \
  --from-literal=OPENAI_API_KEY=your_key \
  -n vla-robot
```

## 🔄 Updates & Maintenance

### Updating Services

```bash
# Pull latest images
docker-compose pull

# Rebuild with new code
docker-compose build --no-cache

# Restart services
docker-compose up -d --force-recreate
```

### Database Backups

```bash
# Postgres backup
docker-compose exec postgres pg_dump -U robot robot_db > backup.sql

# Neo4j backup
docker-compose exec neo4j neo4j-admin dump --to=/backups/neo4j.dump

# Restore
docker-compose exec postgres psql -U robot robot_db < backup.sql
```

### Cleaning Up

```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v

# Clean up images
docker system prune -a
```

## 🐛 Troubleshooting

### Common Issues

**Issue: Port already in use**
```bash
# Find process using port
lsof -i :8000

# Change port in .env
API_PORT=8001
```

**Issue: GPU not detected**
```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

**Issue: Out of memory**
```bash
# Increase Docker memory limit
# Docker Desktop → Settings → Resources → Memory: 8GB+

# Or reduce service replicas
docker-compose up -d --scale perception=1
```

**Issue: Services can't connect**
```bash
# Check network
docker network inspect robot-assistant-vla-sim_vla-network

# Restart networking
docker-compose down
docker network prune
docker-compose up -d
```

### Debug Mode

```bash
# Enable debug logging
echo "LOG_LEVEL=DEBUG" >> .env

# Restart with verbose output
docker-compose up --force-recreate api

# Interactive shell in container
docker-compose exec api /bin/bash
```

## 📚 Additional Resources

- [API Documentation](docs/api.md)
- [Architecture Overview](docs/architecture.md)
- [Development Guide](docs/development.md)
- [ROS2 Integration](docs/ros2.md)

## 🆘 Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/Robot-Assistant-VLA-Sim/issues
- Discussions: https://github.com/yourusername/Robot-Assistant-VLA-Sim/discussions

---

**Deployment Status**: ✅ Production Ready
**Last Updated**: 2025-01-16
