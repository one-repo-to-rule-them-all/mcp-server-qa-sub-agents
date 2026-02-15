"""Repository agent for cloning/updating target repositories."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from .common import sanitize_repo_name

logger = logging.getLogger("qa-council-server")


async def clone_repository(repo_url: str, branch: str, workspace_dir: Path) -> str:
    """Clone or update a GitHub repository for testing."""
    if not repo_url.strip():
        return "❌ Error: Repository URL is required"

    repo_name = sanitize_repo_name(repo_url)
    repo_path = workspace_dir / repo_name

    try:
        if repo_path.exists():
            result = subprocess.run(
                ["git", "-C", str(repo_path), "pull", "origin", branch],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                return f"❌ Repository clone failed: Git pull failed: {result.stderr}"
        else:
            github_token = os.environ.get("GITHUB_TOKEN", "")
            git_url = repo_url.replace("https://", f"https://{github_token}@") if github_token else repo_url
            result = subprocess.run(
                ["git", "clone", "-b", branch, git_url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                return f"❌ Repository clone failed: Git clone failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "❌ Repository clone failed: Git operation timed out"
    except Exception as exc:  # pragma: no cover - defensive guard
        return f"❌ Repository clone failed: {exc}"

    return f"✅ Repository ready at: {repo_path}"
