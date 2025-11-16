#!/bin/bash
# Run test suite

set -e

echo "Running VLA Robot Assistant Tests"
echo "=================================="

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run pytest with coverage
echo "Running pytest..."
pytest tests/ \
    --cov=api \
    --cov=perception \
    --cov=cognition \
    --cov=memory \
    --cov=control \
    --cov-report=html \
    --cov-report=term \
    -v

echo ""
echo "✅ Tests complete!"
echo "Coverage report generated in htmlcov/index.html"
