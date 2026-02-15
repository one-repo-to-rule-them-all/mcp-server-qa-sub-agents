"""CI/CD agent for generating GitHub workflow automation."""

from __future__ import annotations

from pathlib import Path

from .common import verify_path_exists


async def generate_github_workflow(repo_path: str, test_command: str = "pytest") -> str:
    """Generate GitHub Actions workflow for CI/CD testing."""
    if not repo_path.strip():
        return "❌ Error: Repository path is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        return f"❌ Error: {verified_path}"

    workflow_dir = Path(verified_path) / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)

    workflow_content = f'''name: Autonomous QA Testing

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
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

    workflow_file = workflow_dir / "qa_testing.yml"
    workflow_file.write_text(workflow_content, encoding="utf-8")

    return f"✅ GitHub Actions workflow generated\n\n📄 Workflow file: {workflow_file}"
