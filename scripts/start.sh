#!/bin/bash
# Startup script for VLA Robot Assistant
# Launches all services in correct order

set -e

echo "========================================="
echo "Vision-Language Robotic Assistant Startup"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found. Copying from .env.example...${NC}"
    cp .env.example .env
    echo -e "${RED}Please edit .env with your API keys before continuing!${NC}"
    exit 1
fi

# Load environment variables
set -a
source .env
set +a

echo -e "${GREEN}✓ Environment loaded${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker available${NC}"

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker Compose available${NC}"

# Check for GPU
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}✓ NVIDIA GPU detected${NC}"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
    echo -e "${YELLOW}Warning: No NVIDIA GPU detected. Some features may run slowly.${NC}"
fi

echo ""
echo "========================================="
echo "Starting Services..."
echo "========================================="
echo ""

# Build images if needed
if [ "$1" == "--build" ]; then
    echo -e "${YELLOW}Building Docker images...${NC}"
    docker-compose build
    echo -e "${GREEN}✓ Build complete${NC}"
fi

# Start databases first
echo -e "${YELLOW}Starting database services...${NC}"
docker-compose up -d postgres neo4j mongodb redis

# Wait for databases
echo -e "${YELLOW}Waiting for databases to be ready...${NC}"
sleep 10

# Start monitoring
echo -e "${YELLOW}Starting monitoring services...${NC}"
docker-compose up -d prometheus grafana node-exporter

# Start MLOps
echo -e "${YELLOW}Starting MLOps services...${NC}"
docker-compose up -d mlflow

# Start core services
echo -e "${YELLOW}Starting core AI services...${NC}"
docker-compose up -d api agent perception

# Start UI
echo -e "${YELLOW}Starting UI...${NC}"
docker-compose up -d streamlit

# Start simulation (if profile is set)
if [ "$2" == "--sim" ]; then
    echo -e "${YELLOW}Starting Gazebo simulation...${NC}"
    docker-compose --profile simulation up -d gazebo
fi

# Start ROS2 (if profile is set)
if [ "$2" == "--robot" ]; then
    echo -e "${YELLOW}Starting ROS2 nodes...${NC}"
    docker-compose --profile hardware up -d ros2-core
fi

echo ""
echo "========================================="
echo "Startup Complete!"
echo "========================================="
echo ""
echo -e "${GREEN}✓ All services started successfully${NC}"
echo ""
echo "Access points:"
echo "  - API Documentation:  http://localhost:8000/docs"
echo "  - GraphQL Playground: http://localhost:8000/graphql"
echo "  - Streamlit Dashboard: http://localhost:8501"
echo "  - Grafana Monitoring: http://localhost:3000 (admin/admin)"
echo "  - MLflow Tracking:    http://localhost:5000"
echo "  - Neo4j Browser:      http://localhost:7474 (neo4j/robotpassword)"
echo ""
echo "Logs:"
echo "  docker-compose logs -f [service-name]"
echo ""
echo "Stop all services:"
echo "  docker-compose down"
echo ""

# Show running containers
echo "Running containers:"
docker-compose ps

echo ""
echo -e "${GREEN}System ready for commands!${NC}"
