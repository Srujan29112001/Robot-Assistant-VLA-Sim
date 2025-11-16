#!/bin/bash
##############################################################################
# Complete Vision-Language Robotic Assistant Startup Script
# Orchestrates the entire system: ROS2, AI services, APIs, monitoring
##############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0.31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/logs"
ROS2_WS="${PROJECT_DIR}/ros2_ws"

# Create log directory
mkdir -p "${LOG_DIR}"

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a service is running
check_service() {
    local service_name=$1
    local port=$2

    if nc -z localhost $port 2>/dev/null; then
        print_success "$service_name is running on port $port"
        return 0
    else
        print_warning "$service_name is not running on port $port"
        return 1
    fi
}

# Parse arguments
USE_DOCKER=false
USE_SIMULATION=false
USE_ISAAC=false
HEADLESS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --docker)
            USE_DOCKER=true
            shift
            ;;
        --sim|--simulation)
            USE_SIMULATION=true
            shift
            ;;
        --isaac)
            USE_ISAAC=true
            USE_SIMULATION=true
            shift
            ;;
        --headless)
            HEADLESS=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --docker       Use Docker Compose to start services"
            echo "  --sim          Start with Gazebo simulation"
            echo "  --isaac        Use NVIDIA Isaac Sim instead of Gazebo"
            echo "  --headless     Run without GUI (simulation and visualization)"
            echo "  --help         Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

##############################################################################
# Main Startup Sequence
##############################################################################

print_info "========================================"
print_info "Vision-Language Robotic Assistant"
print_info "Complete System Startup"
print_info "========================================"
echo ""

# Check prerequisites
print_info "Checking prerequisites..."

if [ "$USE_DOCKER" = true ]; then
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi

    print_success "Docker and Docker Compose are installed"

    # Start with Docker Compose
    print_info "Starting system with Docker Compose..."

    cd "${PROJECT_DIR}"

    if [ "$USE_SIMULATION" = true ]; then
        print_info "Starting with simulation profile..."
        docker-compose --profile simulation up -d
    else
        print_info "Starting core services..."
        docker-compose up -d
    fi

    print_success "Docker services started"

    # Wait for services to be ready
    print_info "Waiting for services to be ready..."
    sleep 10

else
    # Native installation startup
    print_info "Starting system natively (no Docker)..."

    # Step 1: Start ROS2 system
    print_info "Step 1/7: Starting ROS2 system..."

    if [ ! -d "${ROS2_WS}" ]; then
        print_error "ROS2 workspace not found at ${ROS2_WS}"
        exit 1
    fi

    # Source ROS2
    if [ -f "/opt/ros/humble/setup.bash" ]; then
        source /opt/ros/humble/setup.bash
        print_success "Sourced ROS2 Humble"
    else
        print_error "ROS2 Humble not found. Please install ROS2."
        exit 1
    fi

    # Build ROS2 workspace if needed
    cd "${ROS2_WS}"
    if [ ! -d "install" ]; then
        print_info "Building ROS2 workspace..."
        colcon build --symlink-install
    fi

    source "${ROS2_WS}/install/setup.bash"
    print_success "ROS2 workspace ready"

    # Launch simulation or hardware
    if [ "$USE_SIMULATION" = true ]; then
        if [ "$USE_ISAAC" = true ]; then
            print_info "Launching NVIDIA Isaac Sim..."
            # Launch Isaac Sim (would require Isaac Sim installation)
            print_warning "Isaac Sim launch not yet configured"
        else
            print_info "Launching Gazebo simulation..."
            ros2 launch robot_bringup gazebo_sim.launch.py \
                headless:=${HEADLESS} \
                > "${LOG_DIR}/gazebo.log" 2>&1 &
            sleep 5
        fi
    fi

    # Launch full ROS2 stack
    print_info "Launching complete ROS2 system..."
    ros2 launch robot_bringup full_system.launch.py \
        use_sim_time:=true \
        use_gazebo:=${USE_SIMULATION} \
        > "${LOG_DIR}/ros2_system.log" 2>&1 &

    sleep 5
    print_success "ROS2 system launched"

    # Step 2: Start Database Services
    print_info "Step 2/7: Starting database services..."

    # Neo4j for GraphRAG
    if ! pgrep -f neo4j > /dev/null; then
        print_info "Starting Neo4j..."
        neo4j start > "${LOG_DIR}/neo4j.log" 2>&1 &
    fi

    # PostgreSQL (if needed)
    if ! pgrep -f postgres > /dev/null; then
        print_info "Starting PostgreSQL..."
        pg_ctl start -D /var/lib/postgresql/data > "${LOG_DIR}/postgres.log" 2>&1 || true
    fi

    # MongoDB (if needed)
    if ! pgrep -f mongod > /dev/null; then
        print_info "Starting MongoDB..."
        mongod --fork --logpath "${LOG_DIR}/mongodb.log" || true
    fi

    # Redis
    if ! pgrep -f redis-server > /dev/null; then
        print_info "Starting Redis..."
        redis-server --daemonize yes --logfile "${LOG_DIR}/redis.log"
    fi

    sleep 3
    print_success "Database services started"

    # Step 3: Start Python AI Services
    print_info "Step 3/7: Starting AI/ML services..."

    cd "${PROJECT_DIR}"

    # Activate virtual environment if it exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi

    # Start perception service
    print_info "Starting perception service..."
    python perception/main.py > "${LOG_DIR}/perception.log" 2>&1 &
    PERCEPTION_PID=$!

    # Start LangChain agent
    print_info "Starting LangChain agent..."
    python cognition/agent/langchain_agent.py > "${LOG_DIR}/agent.log" 2>&1 &
    AGENT_PID=$!

    sleep 3
    print_success "AI services started"

    # Step 4: Start FastAPI Backend
    print_info "Step 4/7: Starting FastAPI backend..."

    cd "${PROJECT_DIR}/api"
    uvicorn main:app --host 0.0.0.0 --port 8000 \
        > "${LOG_DIR}/api.log" 2>&1 &
    API_PID=$!

    sleep 5
    print_success "FastAPI backend started"

    # Step 5: Start Monitoring Services
    print_info "Step 5/7: Starting monitoring services..."

    # Prometheus
    if [ -f "${PROJECT_DIR}/monitoring/prometheus/prometheus.yml" ]; then
        prometheus --config.file="${PROJECT_DIR}/monitoring/prometheus/prometheus.yml" \
            --storage.tsdb.path="${PROJECT_DIR}/data/prometheus" \
            > "${LOG_DIR}/prometheus.log" 2>&1 &
    fi

    # Grafana
    if command -v grafana-server &> /dev/null; then
        grafana-server \
            --config="${PROJECT_DIR}/monitoring/grafana/grafana.ini" \
            --homepath=/usr/share/grafana \
            > "${LOG_DIR}/grafana.log" 2>&1 &
    fi

    sleep 3
    print_success "Monitoring services started"

    # Step 6: Start MLflow
    print_info "Step 6/7: Starting MLflow tracking server..."

    mlflow server \
        --backend-store-uri sqlite:///${PROJECT_DIR}/data/mlflow.db \
        --default-artifact-root ${PROJECT_DIR}/data/mlflow-artifacts \
        --host 0.0.0.0 --port 5000 \
        > "${LOG_DIR}/mlflow.log" 2>&1 &

    sleep 2
    print_success "MLflow started"

    # Step 7: Start Streamlit UI
    print_info "Step 7/7: Starting Streamlit dashboard..."

    cd "${PROJECT_DIR}/ui/streamlit"
    streamlit run app.py --server.port 8501 \
        > "${LOG_DIR}/streamlit.log" 2>&1 &
    UI_PID=$!

    sleep 3
    print_success "Streamlit UI started"
fi

##############################################################################
# System Health Check
##############################################################################

print_info ""
print_info "========================================"
print_info "System Health Check"
print_info "========================================"
echo ""

# Check services
check_service "FastAPI" 8000
check_service "Streamlit UI" 8501
check_service "Grafana" 3000
check_service "Prometheus" 9090
check_service "MLflow" 5000

echo ""
print_success "========================================"
print_success "System Startup Complete!"
print_success "========================================"
echo ""

print_info "Access the system:"
echo ""
echo "  📊 Web Dashboard:    http://localhost:8501"
echo "  🔌 API Documentation: http://localhost:8000/docs"
echo "  🔍 GraphQL Playground: http://localhost:8000/graphql"
echo "  📈 Grafana:          http://localhost:3000 (admin/admin)"
echo "  🧪 MLflow:           http://localhost:5000"
echo ""

print_info "Logs are available in: ${LOG_DIR}"
echo ""

print_info "To stop the system, run: ./scripts/stop_system.sh"
echo ""

# Keep script running if not in Docker mode
if [ "$USE_DOCKER" = false ]; then
    print_info "Press Ctrl+C to stop all services..."
    trap 'print_info "Shutting down..."; ./scripts/stop_system.sh; exit 0' INT TERM

    # Wait forever
    while true; do
        sleep 60
    done
fi
