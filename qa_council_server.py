#!/usr/bin/env python3
"""Autonomous QA Testing Council MCP Server.

Slim entry point that delegates all work to specialized agent modules.
Each @mcp.tool() is a thin wrapper around the corresponding agent function.

Architecture:
    qa_council_server.py  (this file — MCP tool registration only)
    ├── agents/repository_agent.py
    ├── agents/analyzer_agent.py
    ├── agents/generator_agent.py
    ├── agents/executor_agent.py
    ├── agents/repair_agent.py
    ├── agents/cicd_agent.py
    └── agents/orchestrator_agent.py
"""
from mcp.server.fastmcp import FastMCP
from utils.config import get_logger, ensure_directories

# ── Server initialization ────────────────────────────────────────────────

logger = get_logger("qa-council-server")
mcp = FastMCP("qa-council")
ensure_directories()

# ── Agent imports ────────────────────────────────────────────────────────

from agents.repository_agent import clone_repository as _clone_repository
from agents.analyzer_agent import run_analysis as _run_analysis
from agents.generator_agent import (
    run_unit_test_generation as _run_unit_test_generation,
    run_e2e_test_generation as _run_e2e_test_generation,
)
from agents.executor_agent import run_test_execution as _run_test_execution
from agents.repair_agent import run_repair_analysis as _run_repair_analysis
from agents.cicd_agent import (
    run_workflow_generation as _run_workflow_generation,
    run_test_fix_pr as _run_test_fix_pr,
)
from agents.orchestrator_agent import (
    orchestrate_full_qa_cycle as _orchestrate_full_qa_cycle,
)

# ── MCP Tool Wrappers ───────────────────────────────────────────────────
# Tool names, parameter names, and types are kept identical to the
# original monolith so existing MCP client configs need zero changes.


@mcp.tool()
async def clone_repository(repo_url: str = "", branch: str = "main") -> str:
    """Clone or update a GitHub repository for testing."""
    return await _clone_repository(repo_url=repo_url, branch=branch)


@mcp.tool()
async def analyze_codebase(repo_path: str = "", file_pattern: str = "*.py") -> str:
    """Analyze Python codebase structure and identify testable components."""
    report, _ = await _run_analysis(repo_path=repo_path)
    return report


@mcp.tool()
async def generate_unit_tests(repo_path: str = "", target_file: str = "") -> str:
    """Generate unit tests for Python functions and classes in a file."""
    return await _run_unit_test_generation(
        repo_path=repo_path, target_file=target_file
    )


@mcp.tool()
async def generate_e2e_tests(
    repo_path: str = "", base_url: str = "", test_name: str = "app"
) -> str:
    """Generate Playwright E2E tests for web applications."""
    return await _run_e2e_test_generation(
        repo_path=repo_path, base_url=base_url
    )


@mcp.tool()
async def execute_tests(repo_path: str = "", test_path: str = "") -> str:
    """Execute pytest tests with coverage reporting."""
    return await _run_test_execution(
        repo_path=repo_path, test_path=test_path
    )


@mcp.tool()
async def repair_failing_tests(repo_path: str = "", test_output: str = "") -> str:
    """Analyze test failures and provide repair suggestions."""
    return await _run_repair_analysis(
        repo_path=repo_path, test_output=test_output
    )


@mcp.tool()
async def generate_github_workflow(
    repo_path: str = "", test_command: str = "pytest"
) -> str:
    """Generate GitHub Actions workflow for CI/CD testing."""
    return await _run_workflow_generation(
        repo_path=repo_path, test_command=test_command
    )


@mcp.tool()
async def create_test_fix_pr(
    repo_url: str = "", test_output: str = "", fixes: str = ""
) -> str:
    """Create GitHub PR with automated test fixes from QA Council analysis."""
    return await _run_test_fix_pr(
        repo_url=repo_url, test_output=test_output, fixes=fixes
    )


@mcp.tool()
async def orchestrate_full_qa_cycle(
    repo_url: str = "", branch: str = "main", base_url: str = ""
) -> str:
    """Execute complete QA lifecycle by calling all specialized agent tools in sequence."""
    return await _orchestrate_full_qa_cycle(
        repo_url=repo_url, branch=branch, base_url=base_url
    )


# ── Server startup ───────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting QA Council MCP Server")
    mcp.run(transport="stdio")
