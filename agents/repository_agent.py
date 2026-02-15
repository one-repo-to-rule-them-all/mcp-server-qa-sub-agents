"""Repository Agent: source code management for the QA Council.

Responsible for cloning, updating, and managing Git repositories
that will be analyzed and tested by other agents.
"""
from utils.config import get_logger
from utils.git_utils import clone_or_update_repo

logger = get_logger("repository")


async def clone_repository(repo_url: str = "", branch: str = "main") -> str:
    """Clone or update a GitHub repository for testing.

    Args:
        repo_url: Full GitHub repository URL
        branch: Git branch to clone/checkout (default: main)

    Returns:
        Status message with repository path or error details.
    """
    if not repo_url.strip():
        return "Error: Repository URL is required"

    logger.info(f"Cloning repository: {repo_url}")
    success, result = clone_or_update_repo(repo_url, branch)

    if success:
        return f"Repository ready at: {result}"
    else:
        return f"Repository clone failed: {result}"
