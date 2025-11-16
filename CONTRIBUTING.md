# Contributing to VLA Robot Assistant

Thank you for your interest in contributing to the Vision-Language Robotic Assistant project!

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a new branch for your feature
4. Make your changes
5. Run tests and linters
6. Submit a pull request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/Robot-Assistant-VLA-Sim.git
cd Robot-Assistant-VLA-Sim

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

## Code Style

We follow PEP 8 with these tools:
- `black` for code formatting
- `isort` for import sorting
- `flake8` for linting
- `mypy` for type checking

Run before committing:
```bash
black .
isort .
flake8 .
mypy .
```

## Testing

All new features must include tests:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test
pytest tests/test_api.py::test_root_endpoint
```

## Pull Request Process

1. Update documentation for any new features
2. Add tests for new functionality
3. Ensure all tests pass
4. Update CHANGELOG.md
5. Request review from maintainers

## Areas for Contribution

### High Priority
- [ ] Additional vision models (SAM, DETIC, etc.)
- [ ] Real robot integration (hardware drivers)
- [ ] Multi-robot coordination
- [ ] Better sim-to-real transfer

### Medium Priority
- [ ] Voice interface improvements
- [ ] Mobile app
- [ ] Additional RL algorithms
- [ ] Better GraphRAG queries

### Documentation
- [ ] Tutorials for different use cases
- [ ] Video demonstrations
- [ ] Architecture deep-dives
- [ ] API examples

## Reporting Issues

When reporting issues, please include:
- System information (OS, GPU, etc.)
- Steps to reproduce
- Expected vs actual behavior
- Logs and error messages
- Screenshots if applicable

## Community Guidelines

- Be respectful and inclusive
- Provide constructive feedback
- Help others in discussions
- Follow the Code of Conduct

## Questions?

- GitHub Discussions: For general questions
- Discord: Real-time chat
- Email: dev@example.com

Thank you for contributing!
