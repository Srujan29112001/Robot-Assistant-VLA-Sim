"""
Setup script for VLA Robot Assistant
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="vla-robot-assistant",
    version="0.1.0",
    author="VLA Team",
    author_email="dev@example.com",
    description="Vision-Language Robotic Assistant with embodied AI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/Robot-Assistant-VLA-Sim",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Scientific/Engineering :: Robotics",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "vla-api=api.main:main",
            "vla-perception=perception.main:main",
            "vla-agent=cognition.agent.main:main",
        ],
    },
)
