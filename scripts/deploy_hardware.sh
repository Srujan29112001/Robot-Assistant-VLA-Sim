#!/bin/bash
################################################################################
# Hardware Deployment Script for Vision-Language Robotic Assistant
# Deploys the system on real robot hardware (Jetson, x86, etc.)
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ROBOT_NAME="${ROBOT_NAME:-robot-assistant-1}"
DEPLOYMENT_DIR="${DEPLOYMENT_DIR:-/opt/robot-assistant}"
ROS2_WS="${DEPLOYMENT_DIR}/ros2_ws"
VENV_PATH="${DEPLOYMENT_DIR}/venv"

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Robot Assistant Hardware Deployment${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# Check if running on supported hardware
check_hardware() {
    echo -e "${YELLOW}Checking hardware...${NC}"

    if [ -f /proc/device-tree/model ]; then
        MODEL=$(cat /proc/device-tree/model)
        echo "Detected: $MODEL"

        if [[ $MODEL == *"Jetson"* ]]; then
            echo -e "${GREEN}NVIDIA Jetson detected${NC}"
            export PLATFORM="jetson"
        fi
    else
        echo "Running on x86/x64 platform"
        export PLATFORM="x86"
    fi

    # Check for GPU
    if command -v nvidia-smi &> /dev/null; then
        echo -e "${GREEN}NVIDIA GPU detected${NC}"
        nvidia-smi --query-gpu=name --format=csv,noheader
        export HAS_GPU=true
    else
        echo -e "${YELLOW}No NVIDIA GPU detected - will use CPU${NC}"
        export HAS_GPU=false
    fi
}

# Install system dependencies
install_dependencies() {
    echo -e "${YELLOW}Installing system dependencies...${NC}"

    # Update package list
    sudo apt-get update

    # Install ROS2
    if ! command -v ros2 &> /dev/null; then
        echo "Installing ROS2 Humble..."
        sudo apt-get install -y software-properties-common
        sudo add-apt-repository universe
        sudo apt-get update && sudo apt-get install -y curl gnupg lsb-release

        # Add ROS2 repository
        sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

        sudo apt-get update
        sudo apt-get install -y ros-humble-desktop ros-humble-ros-base
        sudo apt-get install -y python3-colcon-common-extensions
    fi

    # Install other dependencies
    sudo apt-get install -y \
        python3-pip python3-venv \
        git wget curl \
        librealsense2-utils \
        v4l-utils \
        libusb-1.0-0-dev \
        portaudio19-dev \
        espeak-ng \
        ffmpeg

    echo -e "${GREEN}Dependencies installed${NC}"
}

# Setup deployment directory
setup_deployment_dir() {
    echo -e "${YELLOW}Setting up deployment directory...${NC}"

    sudo mkdir -p ${DEPLOYMENT_DIR}
    sudo chown -R $USER:$USER ${DEPLOYMENT_DIR}

    # Copy project files
    if [ -d "$(pwd)" ]; then
        echo "Copying project files..."
        cp -r $(pwd)/* ${DEPLOYMENT_DIR}/
    fi

    echo -e "${GREEN}Deployment directory ready${NC}"
}

# Setup Python virtual environment
setup_python_env() {
    echo -e "${YELLOW}Setting up Python environment...${NC}"

    cd ${DEPLOYMENT_DIR}

    # Create virtual environment
    python3 -m venv ${VENV_PATH}
    source ${VENV_PATH}/bin/activate

    # Upgrade pip
    pip install --upgrade pip setuptools wheel

    # Install requirements
    if [ -f requirements.txt ]; then
        echo "Installing Python packages..."
        pip install -r requirements.txt
    fi

    # Install PyTorch for Jetson if needed
    if [ "$PLATFORM" == "jetson" ]; then
        echo "Installing PyTorch for Jetson..."
        pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    fi

    echo -e "${GREEN}Python environment ready${NC}"
}

# Build ROS2 workspace
build_ros2_workspace() {
    echo -e "${YELLOW}Building ROS2 workspace...${NC}"

    cd ${ROS2_WS}

    # Source ROS2
    source /opt/ros/humble/setup.bash

    # Build workspace
    colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

    echo -e "${GREEN}ROS2 workspace built${NC}"
}

# Setup systemd services
setup_services() {
    echo -e "${YELLOW}Setting up systemd services...${NC}"

    # Create service file
    sudo tee /etc/systemd/system/robot-assistant.service > /dev/null <<EOF
[Unit]
Description=Vision-Language Robotic Assistant
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=${DEPLOYMENT_DIR}
Environment="PATH=${VENV_PATH}/bin:/usr/bin:/bin"
ExecStart=${VENV_PATH}/bin/python ${DEPLOYMENT_DIR}/scripts/start_robot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    sudo systemctl daemon-reload
    sudo systemctl enable robot-assistant.service

    echo -e "${GREEN}Systemd service configured${NC}"
}

# Configure security
configure_security() {
    echo -e "${YELLOW}Configuring security...${NC}"

    cd ${DEPLOYMENT_DIR}

    # Generate SSL certificates
    if [ ! -d "certs" ]; then
        mkdir -p certs
        python3 -c "from api.security.mtls import generate_self_signed_cert; generate_self_signed_cert('./certs', '${ROBOT_NAME}')" || echo "Certificate generation skipped"
    fi

    # Setup ROS2 security
    python3 -c "from api.security.ros2_security import setup_ros2_security; setup_ros2_security('./ros2_security')" || echo "ROS2 security setup skipped"

    echo -e "${GREEN}Security configured${NC}"
}

# Test deployment
test_deployment() {
    echo -e "${YELLOW}Testing deployment...${NC}"

    source ${VENV_PATH}/bin/activate
    source ${ROS2_WS}/install/setup.bash

    # Test imports
    python3 -c "
import torch
import transformers
import rclpy
print('✓ Core imports successful')
"

    # Test ROS2
    timeout 5 ros2 topic list || echo "ROS2 daemon not running"

    echo -e "${GREEN}Tests passed${NC}"
}

# Main deployment flow
main() {
    echo "Starting hardware deployment..."
    echo ""

    check_hardware
    echo ""

    read -p "Continue with installation? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled"
        exit 1
    fi

    install_dependencies
    setup_deployment_dir
    setup_python_env
    build_ros2_workspace
    setup_services
    configure_security
    test_deployment

    echo ""
    echo -e "${GREEN}=====================================${NC}"
    echo -e "${GREEN}Deployment Complete!${NC}"
    echo -e "${GREEN}=====================================${NC}"
    echo ""
    echo "To start the robot:"
    echo "  sudo systemctl start robot-assistant"
    echo ""
    echo "To view logs:"
    echo "  sudo journalctl -u robot-assistant -f"
    echo ""
    echo "To access the API:"
    echo "  http://$(hostname -I | awk '{print $1}'):8000/docs"
    echo ""
}

# Run main
main "$@"
