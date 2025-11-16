"""Setup configuration for Gemini Key Rotator library."""

from pathlib import Path
from setuptools import setup, find_packages

readme_file = Path(__file__).parent / "readme.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip()
        for line in requirements_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="gemini-key-rotator",
    version="2.0.2",
    author="Vladimir",
    description="High-performance async library with worker-pool architecture and per-slot rate limiting for Google Gemini API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/galkin-v/gemini_key_rotator",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    keywords="google gemini api key-rotation async rate-limiting",
    project_urls={
        "Bug Reports": "https://github.com/galkin-v/gemini-key-rotator/issues",
        "Source": "https://github.com/galkin-v/gemini-key-rotator",
    },
)

