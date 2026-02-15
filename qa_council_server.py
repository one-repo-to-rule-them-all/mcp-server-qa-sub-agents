#!/usr/bin/env python3
"""Autonomous QA Testing Council MCP Server."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from qa_agents.analyzer_agent import analyze_codebase as analyzer_agent_analyze_codebase
from qa_agents.cicd_agent import generate_github_workflow as cicd_agent_generate_github_workflow
from qa_agents.executor_agent import execute_tests as executor_agent_execute_tests
from qa_agents.generator_agent import generate_e2e_tests as generator_agent_generate_e2e_tests
from qa_agents.generator_agent import generate_unit_tests as generator_agent_generate_unit_tests
from qa_agents.github_pr_agent import create_test_fix_pr as github_agent_create_test_fix_pr
from qa_agents.repair_agent import repair_failing_tests as repair_agent_repair_failing_tests
from qa_agents.repository_agent import clone_repository as repository_agent_clone_repository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("qa-council-server")

mcp = FastMCP("qa-council")

WORKSPACE_DIR = Path("/app/repos")
TEST_RESULTS_DIR = Path("/app/test_results")
COVERAGE_DIR = Path("/app/coverage")

WORKSPACE_DIR.mkdir(exist_ok=True)
TEST_RESULTS_DIR.mkdir(exist_ok=True)
COVERAGE_DIR.mkdir(exist_ok=True)


@mcp.tool()
async def clone_repository(repo_url: str = "", branch: str = "main") -> str:
    """Clone or update a GitHub repository for testing."""
    logger.info("Repository Agent: cloning/updating %s", repo_url)
    return await repository_agent_clone_repository(repo_url, branch, WORKSPACE_DIR)


@mcp.tool()
async def analyze_codebase(repo_path: str = "", file_pattern: str = "*.py") -> str:
    """Analyze Python codebase structure and identify testable components."""
    logger.info("Analyzer Agent: analyzing %s", repo_path)
    return await analyzer_agent_analyze_codebase(repo_path, file_pattern)


@mcp.tool()
async def generate_unit_tests(repo_path: str = "", target_file: str = "") -> str:
    """Generate unit tests for supported Python and React source files."""
    logger.info("Generator Agent (unit): generating tests for %s", target_file)
    return await generator_agent_generate_unit_tests(repo_path, target_file)


@mcp.tool()
async def generate_e2e_tests(repo_path: str = "", base_url: str = "", test_name: str = "app") -> str:
    """Generate Playwright E2E tests for web applications."""
    logger.info("Generator Agent (e2e): generating tests for %s", base_url)
    return await generator_agent_generate_e2e_tests(repo_path, base_url, test_name)


@mcp.tool()
async def execute_tests(repo_path: str = "", test_path: str = "") -> str:
    """Execute pytest tests with coverage reporting."""
    logger.info("Executor Agent: running tests in %s", repo_path)
    return await executor_agent_execute_tests(repo_path, TEST_RESULTS_DIR, COVERAGE_DIR, test_path)


@mcp.tool()
async def repair_failing_tests(repo_path: str = "", test_output: str = "") -> str:
    """Analyze test failures and provide repair suggestions."""
    logger.info("Repair Agent: analyzing failures for %s", repo_path)
    return await repair_agent_repair_failing_tests(repo_path, test_output)


@mcp.tool()
async def generate_github_workflow(repo_path: str = "", test_command: str = "pytest") -> str:
    """Generate GitHub Actions workflow for target repositories under test."""
    logger.info("CI/CD Agent: generating workflow for %s", repo_path)
    return await cicd_agent_generate_github_workflow(repo_path, test_command)


@mcp.tool()
async def create_test_fix_pr(repo_url: str = "", test_output: str = "", fixes: str = "") -> str:
    """Create GitHub PR with automated test fixes from QA Council analysis."""
    logger.info("PR Agent: creating test fix PR for %s", repo_url)
    return await github_agent_create_test_fix_pr(repo_url, test_output, fixes, WORKSPACE_DIR)


@mcp.tool()
async def orchestrate_full_qa_cycle(repo_url: str = "", branch: str = "main", base_url: str = "") -> str:
    """Execute complete QA lifecycle by calling specialized agent tools in sequence."""
    if not repo_url.strip():
        return "❌ Error: Repository URL is required"

    results: list[str] = []
    results.extend(["=" * 70, "👤 AGENT 1: REPOSITORY AGENT", "=" * 70])
    clone_result = await clone_repository(repo_url=repo_url, branch=branch)
    results.append(clone_result)
    if "❌" in clone_result:
        return "\n".join(results)

    repo_path = clone_result.split(": ", 1)[1] if ": " in clone_result else ""

    results.extend(["\n" + "=" * 70, "👤 AGENT 2: INSPECTOR/ANALYZER AGENT", "=" * 70])
    results.append(await analyze_codebase(repo_path=repo_path, file_pattern="*.py"))

    results.extend(["\n" + "=" * 70, "👤 AGENT 3: TEST GENERATOR AGENT", "=" * 70])
    generated_count = 0
    for target in ["backend/main.py", "database/database_setup.py", "prestart.py", "frontend/src/App.tsx"]:
        gen_result = await generate_unit_tests(repo_path=repo_path, target_file=target)
        if "✅" in gen_result:
            generated_count += 1
        results.append(f"\n📝 Target: {target}")
        results.append(gen_result[:300])

    if base_url.strip():
        e2e_result = await generate_e2e_tests(repo_path=repo_path, base_url=base_url, test_name="media_tracker")
        results.extend(["\n🌐 E2E Tests:", e2e_result])
        generated_count += 1

    results.extend(["\n" + "=" * 70, "👤 AGENT 4: EXECUTOR AGENT", "=" * 70])
    exec_result = await execute_tests(repo_path=repo_path)
    results.append(exec_result)

    if "failed" in exec_result.lower() or "❌" in exec_result:
        results.extend(["\n" + "=" * 70, "👤 AGENT 5: REPAIRER AGENT", "=" * 70])
        results.append(await repair_failing_tests(repo_path=repo_path, test_output=exec_result))
    else:
        results.append("\n⏭️  Agent 5 (Repairer) skipped - no failures detected")

    results.extend(["\n" + "=" * 70, "👤 AGENT 6: CI/CD AGENT", "=" * 70])
    results.append(await generate_github_workflow(repo_path=repo_path, test_command="pytest --cov=backend --cov-report=xml -v"))

    results.extend([
        "\n" + "=" * 70,
        "✅ COUNCIL OF AGENTS - COMPLETE",
        "=" * 70,
        f"""
📊 Execution Summary:
  ✅ Repository Agent - Code cloned to {repo_path}
  ✅ Inspector Agent - Codebase analyzed
  ✅ Generator Agent - {generated_count} test suites created
  ✅ Executor Agent - Tests executed with coverage
  {"✅ Repairer Agent - Failures analyzed" if "failed" in exec_result.lower() else "⏭️  Repairer Agent - Skipped (no failures)"}
  ✅ CI/CD Agent - GitHub Actions workflow generated
""",
    ])

    return "\n".join(results)


if __name__ == "__main__":
    logger.info("Starting Autonomous QA Testing Council MCP server...")
    logger.info("Workspace directory: %s", WORKSPACE_DIR)
    logger.info("Test results directory: %s", TEST_RESULTS_DIR)
    logger.info("Coverage directory: %s", COVERAGE_DIR)
    mcp.run(transport="stdio")
