"""Path manipulation and verification utilities."""
import os
import re
from pathlib import Path


def sanitize_repo_name(repo_url: str) -> str:
    """Extract safe directory name from repo URL."""
    name = repo_url.rstrip('/').split('/')[-1]
    if name.endswith('.git'):
        name = name[:-4]
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)


def extract_github_info(repo_url: str) -> tuple:
    """Extract owner and repo name from GitHub URL.

    Returns:
        Tuple of (owner, repo_name) or (None, None) if not a GitHub URL.
    """
    parts = repo_url.rstrip('/').split('/')
    if 'github.com' in repo_url:
        owner = parts[-2]
        repo = parts[-1].replace('.git', '')
        return owner, repo
    return None, None


def verify_path_exists(path: str) -> tuple:
    """Verify path exists and is accessible.

    Uses multiple verification methods for Docker container compatibility.

    Returns:
        Tuple of (exists: bool, verified_path_or_error: str)
    """
    try:
        p = Path(path)
        # Try multiple verification methods
        if p.exists():
            return True, str(p)

        # Try using os.path.exists as fallback
        if os.path.exists(path):
            return True, path

        # Try listing parent directory to verify
        parent = p.parent
        if parent.exists():
            children = list(parent.iterdir())
            for child in children:
                if child.name == p.name:
                    return True, str(child)

        return False, f"Path not found: {path}"
    except Exception as e:
        return False, f"Path verification error: {str(e)}"
