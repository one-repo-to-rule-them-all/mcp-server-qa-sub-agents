"""CI/CD Agent: pipeline automation and PR management.

Responsible for generating GitHub Actions workflow files and
creating pull requests with automated test fixes.
"""
import json
from pathlib import Path
from datetime import datetime

from utils.config import GITHUB_TOKEN, WORKSPACE_DIR, get_logger
from utils.path_utils import verify_path_exists, sanitize_repo_name, extract_github_info
from utils.git_utils import create_test_fix_branch, create_github_pr

logger = get_logger("cicd")


async def run_workflow_generation(
    repo_path: str = "", test_command: str = "pytest"
) -> str:
    """Generate GitHub Actions workflow for CI/CD testing.

    Args:
        repo_path: Path to the repository
        test_command: pytest command to use in the workflow

    Returns:
        Status message with workflow file path and feature list.
    """
    if not repo_path.strip():
        return "Error: Repository path is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        return f"Error: {verified_path}"

    logger.info(f"Generating GitHub workflow for: {verified_path}")

    try:
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

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: false

    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: test-results
        path: |
          .coverage
          coverage.xml
          htmlcov/
'''

        workflow_file = workflow_dir / "qa_testing.yml"
        with open(workflow_file, 'w') as f:
            f.write(workflow_content)

        return f"""GitHub Actions workflow generated

Workflow file: {workflow_file}

Features included:
- Runs on push and pull requests
- Python 3.11 environment
- Pytest with coverage reporting
- Playwright E2E testing
- Codecov integration
- Test artifact uploads

Next steps:
1. Commit workflow file to repository
2. Push to GitHub
3. Check Actions tab for test results
"""
    except Exception as e:
        logger.error(f"Workflow generation error: {e}")
        return f"Error generating workflow: {str(e)}"


async def run_test_fix_pr(
    repo_url: str = "", test_output: str = "", fixes: str = ""
) -> str:
    """Create GitHub PR with automated test fixes from QA Council analysis.

    Args:
        repo_url: GitHub repository URL
        test_output: Raw pytest output with failures
        fixes: JSON string of fix objects with 'file', 'content', 'description' keys

    Returns:
        Status message with PR URL or error details.
    """
    if not repo_url.strip():
        return "Error: Repository URL is required"

    owner, repo = extract_github_info(repo_url)
    if not owner or not repo:
        return "Error: Invalid GitHub repository URL"

    if not GITHUB_TOKEN:
        return "Error: GITHUB_TOKEN not configured. Set it as an environment variable."

    logger.info(f"Creating test fix PR for {owner}/{repo}")

    try:
        repo_name = sanitize_repo_name(repo_url)
        repo_path = str(WORKSPACE_DIR / repo_name)

        branch_name = (
            f"qa-council/test-fixes-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )

        # Parse fixes (expect JSON string)
        try:
            fix_list = json.loads(fixes) if fixes.strip() else []
        except Exception:
            fix_list = []

        if fix_list:
            success, result = await create_test_fix_branch(
                repo_path, branch_name, fix_list
            )
            if not success:
                return f"Failed to create fix branch: {result}"

        pr_title = "Automated Test Fixes from QA Council"
        fix_descriptions = "\n".join(
            [f"- {fix.get('description', 'Test fix')}" for fix in fix_list]
        ) if fix_list else "- Analysis and recommendations provided"

        pr_body = f"""## Automated Test Repair Analysis

This PR contains automated fixes suggested by the QA Council multi-agent system.

### Analysis Summary
{test_output[:500] if test_output else 'Test analysis completed'}

### Fixes Applied
{fix_descriptions}

### Next Steps
1. Review the changes carefully
2. Run tests locally: `pytest -v`
3. Merge if all tests pass

---
*Generated by QA Council Autonomous Testing System*
"""

        success, pr_url = await create_github_pr(
            owner, repo, pr_title, pr_body, branch_name
        )

        if success:
            return f"""Pull Request Created Successfully

PR URL: {pr_url}
Branch: {branch_name}

The PR includes:
- Automated test fixes
- Detailed analysis
- Repair recommendations

Review and merge when ready!
"""
        else:
            return f"Failed to create PR: {pr_url}"
    except Exception as e:
        logger.error(f"PR creation error: {e}")
        return f"Error creating PR: {str(e)}"
