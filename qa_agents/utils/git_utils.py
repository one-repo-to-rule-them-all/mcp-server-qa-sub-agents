"""Git URL and repository parsing helpers."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def sanitize_repo_name(repo_url: str) -> str:
    """Extract a safe directory name from a repository URL."""
    name = repo_url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def build_git_clone_url(repo_url: str, github_token: str = "") -> str:
    """Inject a GitHub token into an HTTPS clone URL when provided."""
    if not github_token:
        return repo_url
    if repo_url.startswith("https://"):
        return repo_url.replace("https://", f"https://{github_token}@", 1)
    return repo_url


def parse_github_repo_identifier(repo_url: str) -> str:
    """Parse a GitHub URL into owner/repo form."""
    cleaned = repo_url.strip()
    if cleaned.startswith("git@github.com:"):
        cleaned = cleaned.split(":", 1)[1]
    elif "github.com/" in cleaned:
        cleaned = cleaned.split("github.com/", 1)[1]

    cleaned = cleaned.rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]

    parts = cleaned.split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return ""


def get_repo_identifier_from_local_repo(repo_path: str | Path) -> str:
    """Read origin remote URL from a local git repository and return owner/repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return ""

    if result.returncode != 0:
        return ""

    return parse_github_repo_identifier(result.stdout.strip())
