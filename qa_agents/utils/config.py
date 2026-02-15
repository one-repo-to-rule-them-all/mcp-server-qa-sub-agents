"""Configuration helpers for shared QA Council paths and settings."""

from __future__ import annotations

import os
from pathlib import Path


def get_directory_from_env(env_name: str, default_path: str) -> Path:
    """Return a directory path from env, ensuring it exists."""
    configured = os.environ.get(env_name, default_path)
    directory = Path(configured)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_github_token() -> str:
    """Return GitHub token from environment if configured."""
    return os.environ.get("GITHUB_TOKEN", "")
