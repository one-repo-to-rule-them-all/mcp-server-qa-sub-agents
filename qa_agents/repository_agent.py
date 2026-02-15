"""Repository agent for cloning/updating target repositories."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from .common import sanitize_repo_name

logger = logging.getLogger("qa-council-server.repository-agent")


async def clone_repository(repo_url: str, branch: str, workspace_dir: Path) -> str:
    """Clone or update a GitHub repository for testing."""
    logger.info("Starting repository sync: repo_url=%s branch=%s", repo_url, branch)

    if not repo_url.strip():
        logger.warning("Repository sync aborted: repository URL was empty")
        return "❌ Error: Repository URL is required"

    repo_name = sanitize_repo_name(repo_url)
    repo_path = workspace_dir / repo_name

    try:
        if repo_path.exists():
            logger.info("Updating existing repository at %s", repo_path)
            result = subprocess.run(
                ["git", "-C", str(repo_path), "pull", "origin", branch],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                logger.error("Git pull failed for %s: %s", repo_path, result.stderr)
                return f"❌ Repository clone failed: Git pull failed: {result.stderr}"
        else:
            logger.info("Cloning new repository into %s", repo_path)
            github_token = os.environ.get("GITHUB_TOKEN", "")
            git_url = repo_url.replace("https://", f"https://{github_token}@") if github_token else repo_url
            result = subprocess.run(
                ["git", "clone", "-b", branch, git_url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.error("Git clone failed for %s: %s", repo_url, result.stderr)
                return f"❌ Repository clone failed: Git clone failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        logger.error("Repository sync timed out for %s", repo_url)
        return "❌ Repository clone failed: Git operation timed out"
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Repository sync failed unexpectedly")
        return f"❌ Repository clone failed: {exc}"

    logger.info("Repository ready at %s", repo_path)
    return f"✅ Repository ready at: {repo_path}"
