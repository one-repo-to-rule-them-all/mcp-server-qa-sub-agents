"""Git operations: clone, branch creation, PR submission."""
import subprocess
import json
from pathlib import Path
from datetime import datetime
import httpx

from utils.config import GITHUB_TOKEN, WORKSPACE_DIR, get_logger
from utils.path_utils import sanitize_repo_name

logger = get_logger("git")


def clone_or_update_repo(repo_url: str, branch: str = "main") -> tuple:
    """Clone or update a GitHub repository.

    Returns:
        Tuple of (success: bool, repo_path_or_error: str)
    """
    repo_name = sanitize_repo_name(repo_url)
    repo_path = WORKSPACE_DIR / repo_name

    try:
        if repo_path.exists():
            logger.info(f"Updating existing repo: {repo_name}")
            result = subprocess.run(
                ["git", "-C", str(repo_path), "pull", "origin", branch],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                return False, f"Git pull failed: {result.stderr}"
        else:
            logger.info(f"Cloning new repo: {repo_name}")
            git_url = repo_url
            if GITHUB_TOKEN:
                git_url = repo_url.replace("https://", f"https://{GITHUB_TOKEN}@")

            result = subprocess.run(
                ["git", "clone", "-b", branch, git_url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                return False, f"Git clone failed: {result.stderr}"

        return True, str(repo_path)
    except subprocess.TimeoutExpired:
        return False, "Git operation timed out"
    except Exception as e:
        return False, str(e)


async def create_github_pr(
    owner: str, repo: str, title: str, body: str,
    head_branch: str, base_branch: str = "main"
) -> tuple:
    """Create a GitHub Pull Request.

    Returns:
        Tuple of (success: bool, pr_url_or_error: str)
    """
    if not GITHUB_TOKEN:
        return False, "GitHub token not configured"

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "title": title,
        "body": body,
        "head": head_branch,
        "base": base_branch
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 201:
                pr_data = response.json()
                return True, pr_data["html_url"]
            else:
                return False, f"GitHub API error: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"Error creating PR: {str(e)}"


async def create_test_fix_branch(
    repo_path: str, branch_name: str, fixes: list
) -> tuple:
    """Create a new branch with test fixes applied.

    Args:
        repo_path: Path to the repository
        branch_name: Name of the new branch
        fixes: List of dicts with 'file' and 'content' keys

    Returns:
        Tuple of (success: bool, branch_name_or_error: str)
    """
    try:
        # Create new branch
        result = subprocess.run(
            ["git", "-C", repo_path, "checkout", "-b", branch_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return False, f"Failed to create branch: {result.stderr}"

        # Apply fixes (write fix files)
        for fix in fixes:
            file_path = Path(repo_path) / fix["file"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                f.write(fix["content"])

        # Stage changes
        subprocess.run(
            ["git", "-C", repo_path, "add", "."],
            check=True, timeout=10
        )

        # Commit
        subprocess.run(
            ["git", "-C", repo_path, "commit", "-m",
             "fix: Apply automated test repairs from QA Council"],
            check=True, timeout=10
        )

        # Push
        subprocess.run(
            ["git", "-C", repo_path, "push", "-u", "origin", branch_name],
            capture_output=True, text=True, timeout=30
        )

        return True, branch_name
    except Exception as e:
        return False, f"Error creating fix branch: {str(e)}"
