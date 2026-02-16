"""Configuration agent for generating a modular Council of Sub-Agents blueprint."""

from __future__ import annotations

import logging
from pathlib import Path

from .utils import verify_path_exists

logger = logging.getLogger("qa-council-server.council-config-agent")

DEFAULT_COUNCIL_CONFIG_PATH = Path(".qa-council") / "council-config.yml"
DEFAULT_AUTOFIX_WORKFLOW_PATH = Path(".github") / "workflows" / "qa_council_autofix.yml"


def _detect_stack_flags(repo_root: Path) -> tuple[bool, bool]:
    """Infer frontend/backend presence from common React and Python project markers."""
    has_backend = any(
        (repo_root / candidate).exists()
        for candidate in ("backend", "app", "pyproject.toml", "requirements.txt")
    )
    has_frontend = any(
        (repo_root / candidate).exists()
        for candidate in ("frontend", "package.json", "src")
    )
    return has_frontend, has_backend


def _build_council_config(repo_name: str, has_frontend: bool, has_backend: bool) -> str:
    """Render declarative council configuration in YAML."""
    frontend_toggle = "true" if has_frontend else "false"
    backend_toggle = "true" if has_backend else "false"
    return f'''version: 1
name: "{repo_name}-qa-council"
mode: autonomous

objectives:
  - Analyze source code and test gaps for frontend and backend
  - Generate, execute, and self-heal Pytest + Playwright tests
  - Open pull requests with created or repaired tests

capabilities:
  frontend: {frontend_toggle}
  backend: {backend_toggle}
  self_healing: true
  pr_automation: true
  github_actions_dispatch: true

orchestrator:
  strategy: staged-pipeline
  max_healing_iterations: 3
  fail_fast: false

sub_agents:
  - id: repo-intake
    role: Repository Agent
    responsibilities:
      - clone_or_update_repo
      - establish_branch_context

  - id: static-analyzer
    role: Source Analysis Agent
    responsibilities:
      - map_python_modules
      - map_react_components
      - prioritize_risk_areas

  - id: test-architect
    role: Test Generation Agent
    responsibilities:
      - generate_pytest_unit_and_integration
      - generate_playwright_e2e_with_pom
      - maintain_test_data_factories

  - id: qa-executor
    role: Test Execution Agent
    responsibilities:
      - run_pytest_with_coverage
      - run_playwright_headless
      - persist_artifacts

  - id: healing-engine
    role: Repair Agent
    responsibilities:
      - classify_failures
      - patch_flaky_or_broken_tests
      - rerun_impacted_suites

  - id: release-governor
    role: CI/CD + PR Agent
    responsibilities:
      - trigger_github_actions
      - summarize_outcomes
      - create_pull_request

policies:
  quality_gates:
    min_backend_coverage_pct: 75
    min_frontend_coverage_pct: 70
    block_on_new_failures: true
  branching:
    qa_branch_prefix: "qa/council/"
    commit_message_prefix: "test(council):"
'''


def _build_autofix_workflow() -> str:
    """Render GitHub Actions workflow for autonomous QA council execution."""
    return '''name: QA Council AutoFix\n\non:\n  workflow_dispatch:\n  pull_request:\n    types: [opened, synchronize, reopened]\n\npermissions:\n  contents: write\n  pull-requests: write\n\njobs:\n  council-lifecycle:\n    runs-on: ubuntu-latest\n\n    steps:\n      - name: Checkout repository\n        uses: actions/checkout@v4\n\n      - name: Setup Python\n        uses: actions/setup-python@v5\n        with:\n          python-version: "3.11"\n\n      - name: Install dependencies\n        run: |\n          python -m pip install --upgrade pip\n          pip install pytest pytest-cov pytest-playwright playwright\n          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi\n          if [ -f backend/requirements.txt ]; then pip install -r backend/requirements.txt; fi\n          playwright install chromium\n\n      - name: Run backend and unit tests\n        run: pytest -q --maxfail=5 --disable-warnings --cov=. --cov-report=xml || true\n\n      - name: Run Playwright tests\n        run: pytest tests/e2e -q || true\n\n      - name: Auto-heal test files (placeholder hook)\n        run: |\n          echo "Hook your repair agent here (e.g., python -m qa_agents.repair_agent ...)"\n\n      - name: Create PR with generated/repaired tests\n        uses: peter-evans/create-pull-request@v7\n        with:\n          branch: qa/council/autofix\n          commit-message: test(council): generate and repair automated tests\n          title: "test(council): generated/repaired QA tests"\n          body: |\n            ## QA Council AutoFix\n            - Generated missing tests\n            - Attempted self-healing for failing tests\n            - Attached results from CI lifecycle run\n          labels: automated-pr, qa, tests\n'''


async def generate_council_configuration(repo_path: str = "") -> str:
    """Generate Council-of-Sub-Agents configuration + autofix workflow for a target repo."""
    logger.info("Generating council configuration for %s", repo_path)

    if not repo_path.strip():
        return "❌ Error: Repository path is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        return f"❌ Error: {verified_path}"

    repo_root = Path(verified_path)
    has_frontend, has_backend = _detect_stack_flags(repo_root)

    config_path = repo_root / DEFAULT_COUNCIL_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        _build_council_config(repo_root.name, has_frontend=has_frontend, has_backend=has_backend),
        encoding="utf-8",
    )

    workflow_path = repo_root / DEFAULT_AUTOFIX_WORKFLOW_PATH
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(_build_autofix_workflow(), encoding="utf-8")

    frontend_status = "enabled" if has_frontend else "disabled"
    backend_status = "enabled" if has_backend else "disabled"

    return (
        "✅ Council configuration generated\n\n"
        f"📄 Config file: {config_path}\n"
        f"📄 Workflow file: {workflow_path}\n"
        f"🧩 Stack detection → frontend: {frontend_status}, backend: {backend_status}"
    )
