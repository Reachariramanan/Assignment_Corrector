"""
Setup configuration for Yukta Agent System
All necessary packages are installed by default.
No optional extras needed - everything you need comes with a single install.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    with open(readme_file, "r", encoding="utf-8") as f:
        long_description = f.read()

# Read requirements - ALL packages are installed by default
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file, "r", encoding="utf-8") as f:
        requirements = [
            line.strip() 
            for line in f 
            if line.strip() and not line.startswith("#") and not line.startswith("=")
        ]

setup(
    name="yukta",
    version="2.1.0",
    author="VCoder4646",
    author_email="vasanthwork0475@gmail.com",
    description="A comprehensive, modular agent system with Memory management, KV cache optimization, and cost-efficient LLM integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/VCoder4646/yukta",
    packages=find_packages(exclude=["tests", "tests.*", "examples", "examples.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    # All essential packages installed by default
    install_requires=requirements,
    # Development tools are optional
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="agent llm ai memory tools cache",
    project_urls={
        "Bug Reports": "https://github.com/VCoder4646/yukta/issues",
        "Source": "https://github.com/VCoder4646/yukta",
        "Documentation": "https://github.com/VCoder4646/yukta/blob/main/README.md",
    },
)