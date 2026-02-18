"""GitHub PR agent.

This module creates fix branches and pull requests for generated QA repairs.
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

import httpx

from .utils import get_github_token, sanitize_repo_name

logger = logging.getLogger("qa-council-server.github-pr-agent")


# Default Git identity used when the environment does not provide one.
_DEFAULT_GIT_USER_NAME = "QA Council Bot"
_DEFAULT_GIT_USER_EMAIL = "qa-council-bot@users.noreply.github.com"


def _extract_github_info(repo_url: str) -> tuple[str | None, str | None]:
    """Extract owner/repo metadata from a GitHub URL."""
    parts = repo_url.rstrip("/").split("/")
    if "github.com" not in repo_url or len(parts) < 2:
        return None, None
    owner = parts[-2]
    repo = parts[-1].replace(".git", "")
    return owner, repo


async def _create_github_pr(
    owner: str,
    repo: str,
    title: str,
    body: str,
    head_branch: str,
    base_branch: str = "main",
) -> tuple[bool, str]:
    """Call GitHub API to open a pull request for generated fixes."""
    github_token = get_github_token()
    if not github_token:
        return False, "GitHub token not configured"

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "title": title,
        "body": body,
        "head": head_branch,
        "base": base_branch,
    }

    logger.info("Creating GitHub PR via API: %s/%s head=%s base=%s", owner, repo, head_branch, base_branch)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 201:
            pr_url = response.json().get("html_url", "")
            logger.info("Created GitHub PR successfully: %s", pr_url)
            return True, pr_url
        logger.error("GitHub API returned non-success: %s %s", response.status_code, response.text)
        return False, f"GitHub API error: {response.status_code} - {response.text}"
    except Exception as exc:  # pragma: no cover - network/remote guard
        logger.exception("Error while creating GitHub PR")
        return False, f"Error creating PR: {exc}"


async def _create_test_fix_branch(repo_path: str, branch_name: str, fixes: list[dict]) -> tuple[bool, str]:
    """Create and push a branch with generated fix files."""
    logger.info("Creating test-fix branch: %s in %s (fixes=%d)", branch_name, repo_path, len(fixes))

    try:
        checkout = subprocess.run(
            ["git", "-C", repo_path, "checkout", "-b", branch_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if checkout.returncode != 0:
            logger.error("Failed creating branch: %s", checkout.stderr)
            return False, f"Failed to create branch: {checkout.stderr}"

        for fix in fixes:
            file_path = Path(repo_path) / fix["file"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(fix["content"], encoding="utf-8")

        # Stage all generated repair files before diff/commit checks.
        subprocess.run(["git", "-C", repo_path, "add", "."], check=True, timeout=10)

        diff_check = subprocess.run(
            ["git", "-C", repo_path, "diff", "--cached", "--quiet"],
            timeout=10,
        )
        if diff_check.returncode == 0:
            logger.info("No staged changes detected after applying fixes; skipping commit/push")
            return True, "no_changes"

        _ensure_local_git_identity(repo_path)

        subprocess.run(
            ["git", "-C", repo_path, "commit", "-m", "fix: Apply automated test repairs from QA Council"],
            check=True,
            timeout=10,
        )

        push = subprocess.run(
            ["git", "-C", repo_path, "push", "-u", "origin", branch_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if push.returncode != 0:
            logger.error("Failed pushing branch: %s", push.stderr)
            return False, f"Failed to push branch: {push.stderr}"

        logger.info("Created and pushed test-fix branch successfully: %s", branch_name)
        return True, branch_name
    except Exception as exc:  # pragma: no cover - git/runtime guard
        logger.exception("Error while creating test-fix branch")
        return False, f"Error creating fix branch: {exc}"


def _ensure_local_git_identity(repo_path: str) -> None:
    """Ensure repository-local git identity exists so non-interactive commits can succeed."""
    configured_name = subprocess.run(
        ["git", "-C", repo_path, "config", "--get", "user.name"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    configured_email = subprocess.run(
        ["git", "-C", repo_path, "config", "--get", "user.email"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Configure only missing fields to avoid overriding repository-specific settings.
    if configured_name.returncode != 0 or not configured_name.stdout.strip():
        subprocess.run(
            ["git", "-C", repo_path, "config", "user.name", _DEFAULT_GIT_USER_NAME],
            check=True,
            timeout=10,
        )
    if configured_email.returncode != 0 or not configured_email.stdout.strip():
        subprocess.run(
            ["git", "-C", repo_path, "config", "user.email", _DEFAULT_GIT_USER_EMAIL],
            check=True,
            timeout=10,
        )


async def create_test_fix_pr(repo_url: str, test_output: str, fixes: str, workspace_dir: Path) -> str:
    """Create GitHub PR with automated test fixes from QA Council analysis."""
    logger.info("Starting PR creation flow for repo URL: %s", repo_url)

    if not repo_url.strip():
        logger.warning("PR creation aborted: repository URL was empty")
        return "❌ Error: Repository URL is required"

    owner, repo = _extract_github_info(repo_url)
    if not owner or not repo:
        logger.warning("PR creation aborted: invalid GitHub URL (%s)", repo_url)
        return "❌ Error: Invalid GitHub repository URL"

    if not get_github_token():
        logger.warning("PR creation aborted: no GitHub token was configured")
        return "❌ Error: GitHub token not configured. Set GITHUB_TOKEN (or GH_TOKEN/GITHUB_PAT)."

    repo_name = sanitize_repo_name(repo_url)
    repo_path = str(workspace_dir / repo_name)
    branch_name = f"qa-council/test-fixes-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Parse optional fix payload from orchestrator output.
    try:
        fix_list = json.loads(fixes) if fixes.strip() else []
    except Exception:
        logger.warning("Fix payload was not valid JSON; proceeding without file changes")
        fix_list = []

    if fix_list:
        success, branch_result = await _create_test_fix_branch(repo_path, branch_name, fix_list)
        if not success:
            return f"❌ Failed to create fix branch: {branch_result}"
        if branch_result == "no_changes":
            logger.info("No code changes detected from generated fixes; skipping PR creation")
            return "⚠️ No code changes were produced by generated fixes, so no PR was created."

    pr_title = "🤖 Automated Test Fixes from QA Council"
    pr_body = f"""## 🤖 Automated Test Repair Analysis

This PR contains automated fixes suggested by the QA Council multi-agent system.

### 📊 Analysis Summary
{test_output[:500] if test_output else 'Test analysis completed'}

### 🔧 Fixes Applied
{chr(10).join([f"- {fix.get('description', 'Test fix')}" for fix in fix_list]) if fix_list else '- Analysis and recommendations provided'}

### ✅ Next Steps
1. Review the changes carefully
2. Run tests locally: `pytest -v`
3. Merge if all tests pass

---
*Generated by QA Council Autonomous Testing System*
"""

    success, pr_url = await _create_github_pr(owner, repo, pr_title, pr_body, branch_name)
    if not success:
        return f"❌ Failed to create PR: {pr_url}"

    return f"""✅ Pull Request Created Successfully

🔗 PR URL: {pr_url}
📝 Branch: {branch_name}
🤖 Generated by: QA Council

The PR includes:
- Automated test fixes
- Detailed analysis
- Repair recommendations

Review and merge when ready!
"""
