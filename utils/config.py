"""Shared configuration for QA Council agents."""
import os
import sys
import logging
from pathlib import Path

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)


def get_logger(name: str) -> logging.Logger:
    """Create a namespaced logger for a QA Council component."""
    return logging.getLogger(f"qa-council.{name}")


# Environment configuration
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Directory paths (support env var overrides for flexibility)
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/app/repos"))
TEST_RESULTS_DIR = Path(os.environ.get("TEST_RESULTS_DIR", "/app/test_results"))
COVERAGE_DIR = Path(os.environ.get("COVERAGE_DIR", "/app/coverage"))


def ensure_directories():
    """Create required directories if they don't exist."""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    COVERAGE_DIR.mkdir(parents=True, exist_ok=True)
