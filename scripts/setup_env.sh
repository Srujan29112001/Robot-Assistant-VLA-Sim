#!/bin/bash
# Setup script for VLA Robot Assistant

set -e

echo "==================================="
echo "VLA Robot Assistant - Setup Script"
echo "==================================="

# Check if running in correct directory
if [ ! -f "docker-compose.yml" ]; then
    echo "Error: Please run this script from the project root directory"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your API keys before proceeding"
fi

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

echo "✅ Docker found"

# Check for Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker Compose found"

# Create necessary directories
echo "Creating directories..."
mkdir -p models data/datasets logs

# Pull required Docker images (optional, will be built anyway)
echo "This will build all Docker images (may take 10-30 minutes)..."
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose build
    echo "✅ Docker images built successfully"
fi

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys"
echo "2. Run: docker-compose up"
echo "3. Access the dashboard at http://localhost:8501"
echo ""
