"""
Setup script for SafeSim
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="safesim",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@umd.edu",
    description="Safe Medical Text Simplification with Neuro-Symbolic Verification",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/safesim",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "streamlit>=1.28.0",
        "spacy>=3.7.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "openai>=1.3.0",
        "anthropic>=0.7.0",
        "transformers>=4.35.0",
        "torch>=2.0.0",
        "pytest>=7.4.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
        "scispacy": [
            "scispacy>=0.5.3",
        ],
    },
    entry_points={
        "console_scripts": [
            "safesim=src.ui.app:main",
        ],
    },
)
