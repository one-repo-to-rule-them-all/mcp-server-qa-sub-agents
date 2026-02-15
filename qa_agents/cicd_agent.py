"""CI/CD agent for generating GitHub workflow automation."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from .utils import get_github_token, get_repo_identifier_from_local_repo, verify_path_exists

logger = logging.getLogger("qa-council-server.cicd-agent")

DEFAULT_DISPATCH_REPO = "one-repo-to-rule-them-all/media-collection-tracker"
DEFAULT_WORKFLOW_FILE = "qa_testing.yml"


async def _trigger_github_workflow(
    repo_identifier: str,
    workflow_file: str,
    ref: str,
    github_token: str,
) -> tuple[bool, str]:
    """Trigger a workflow_dispatch event for a GitHub Actions workflow."""
    if not github_token:
        return False, "⚠️ Workflow dispatch skipped: GITHUB_TOKEN is not configured"

    if not repo_identifier:
        return False, "⚠️ Workflow dispatch skipped: repository identifier is missing"

    dispatch_url = f"https://api.github.com/repos/{repo_identifier}/actions/workflows/{workflow_file}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"ref": ref}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(dispatch_url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        logger.warning("Workflow dispatch failed due to network/HTTP issue: %s", exc)
        return False, f"⚠️ Workflow dispatch failed: {exc}"

    if response.status_code == 204:
        return True, f"🚀 Triggered GitHub workflow '{workflow_file}' in {repo_identifier} on ref '{ref}'"

    if response.status_code == 401:
        logger.warning("Workflow dispatch unauthorized for %s", repo_identifier)
        return (
            False,
            "⚠️ Workflow dispatch failed (401 Unauthorized): the configured GitHub token is invalid, expired, "
            "or missing 'repo' + 'workflow' scopes.",
        )

    logger.warning("Workflow dispatch failed: status=%s body=%s", response.status_code, response.text)
    return (
        False,
        f"⚠️ Workflow dispatch failed ({response.status_code}): {response.text[:400]}",
    )


async def generate_github_workflow(
    repo_path: str,
    test_command: str = "pytest",
    trigger_workflow: str = "true",
    workflow_repo: str = DEFAULT_DISPATCH_REPO,
    workflow_ref: str = "main",
) -> str:
    """Generate GitHub Actions workflow for CI/CD testing and optionally trigger workflow_dispatch."""
    logger.info(
        "Generating workflow: repo_path=%s trigger=%s workflow_repo=%s",
        repo_path,
        trigger_workflow,
        workflow_repo,
    )

    if not repo_path.strip():
        logger.warning("Workflow generation aborted: repository path was empty")
        return "❌ Error: Repository path is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        logger.warning("Workflow generation aborted: invalid repository path (%s)", verified_path)
        return f"❌ Error: {verified_path}"

    workflow_dir = Path(verified_path) / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)

    workflow_content = f'''name: Autonomous QA Testing

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest pytest-cov playwright httpx
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
        if [ -f backend/requirements.txt ]; then pip install -r backend/requirements.txt; fi
        playwright install chromium
        playwright install-deps chromium

    - name: Run tests with coverage
      run: |
        {test_command} --cov=. --cov-report=xml --cov-report=term
'''

    workflow_file = workflow_dir / DEFAULT_WORKFLOW_FILE
    workflow_file.write_text(workflow_content, encoding="utf-8")
    logger.info("Workflow generated at %s", workflow_file)

    should_trigger = trigger_workflow.strip().lower() in {"true", "1", "yes", "y"}
    dispatch_status = "⏭️ Workflow dispatch skipped by configuration"
    if should_trigger:
        inferred_repo = get_repo_identifier_from_local_repo(verified_path)
        dispatch_repo = inferred_repo or workflow_repo
        github_token = get_github_token()
        _, dispatch_status = await _trigger_github_workflow(
            repo_identifier=dispatch_repo,
            workflow_file=DEFAULT_WORKFLOW_FILE,
            ref=workflow_ref,
            github_token=github_token,
        )

    return (
        "✅ GitHub Actions workflow generated\n\n"
        f"📄 Workflow file: {workflow_file}\n"
        f"{dispatch_status}"
    )
