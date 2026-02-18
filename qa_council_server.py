#!/usr/bin/env python3
"""Autonomous QA Testing Council MCP Server."""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from qa_agents.analyzer_agent import analyze_codebase as analyzer_agent_analyze_codebase
from qa_agents.analyzer_agent import discover_unit_test_targets as analyzer_agent_discover_unit_test_targets
from qa_agents.cicd_agent import generate_github_workflow as cicd_agent_generate_github_workflow
from qa_agents.executor_agent import execute_tests as executor_agent_execute_tests
from qa_agents.generator_agent import generate_e2e_tests as generator_agent_generate_e2e_tests
from qa_agents.generator_agent import generate_unit_tests as generator_agent_generate_unit_tests
from qa_agents.github_pr_agent import create_test_fix_pr as github_agent_create_test_fix_pr
from qa_agents.repair_agent import repair_failing_tests as repair_agent_repair_failing_tests
from qa_agents.repository_agent import clone_repository as repository_agent_clone_repository
from qa_agents.utils import get_directory_from_env

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("qa-council-server")

mcp = FastMCP("qa-council")

WORKSPACE_DIR = get_directory_from_env("WORKSPACE_DIR", "/app/repos")
TEST_RESULTS_DIR = get_directory_from_env("TEST_RESULTS_DIR", "/app/test_results")
COVERAGE_DIR = get_directory_from_env("COVERAGE_DIR", "/app/coverage")


@dataclass
class GeneratedArtifact:
    """Generated file metadata used to open pull requests with concrete changes."""

    relative_path: str
    description: str

def _extract_generated_artifact(repo_path: str, generator_output: str) -> GeneratedArtifact | None:
    """Extract generated file path from a generator message."""
    match = re.search(r"(?:📝 Test file|📄 Workflow file):\s*(.+)", generator_output)
    if not match:
        return None

    generated_path = Path(match.group(1).strip())
    if not generated_path.exists():
        return None

    repo = Path(repo_path)
    try:
        relative_path = str(generated_path.relative_to(repo))
    except ValueError:
        return None

    return GeneratedArtifact(relative_path=relative_path, description=f"Generated tests for {relative_path}")


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
async def generate_github_workflow(
    repo_path: str = "",
    test_command: str = "pytest",
    trigger_workflow: str = "true",
    workflow_repo: str = "one-repo-to-rule-them-all/media-collection-tracker",
    workflow_ref: str = "main",
) -> str:
    """Generate and optionally trigger GitHub Actions workflow for target repositories."""
    logger.info("CI/CD Agent: generating workflow for %s", repo_path)
    return await cicd_agent_generate_github_workflow(
        repo_path=repo_path,
        test_command=test_command,
        trigger_workflow=trigger_workflow,
        workflow_repo=workflow_repo,
        workflow_ref=workflow_ref,
    )


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

    # Orchestrator composes a single narrative from specialist agents.
    results: list[str] = []
    results.extend(["=" * 70, "👤 AGENT 1: REPOSITORY AGENT", "=" * 70])

    logger.info("Orchestration: starting repository agent")
    clone_result = await clone_repository(repo_url=repo_url, branch=branch)
    results.append(clone_result)
    if "❌" in clone_result:
        logger.warning("Orchestration halted after repository stage")
        return "\n".join(results)

    repo_path = clone_result.split(": ", 1)[1] if ": " in clone_result else ""

    results.extend(["\n" + "=" * 70, "👤 AGENT 2: INSPECTOR/ANALYZER AGENT", "=" * 70])
    logger.info("Orchestration: starting analyzer agent")
    analysis_result = await analyze_codebase(repo_path=repo_path, file_pattern="*.py")
    results.append(analysis_result)

    results.extend(["\n" + "=" * 70, "👤 AGENT 3: TEST GENERATOR AGENT", "=" * 70])
    logger.info("Orchestration: starting generator agent")
    generated_count = 0
    generated_artifacts: list[GeneratedArtifact] = []
    unit_test_targets = analyzer_agent_discover_unit_test_targets(Path(repo_path))
    if not unit_test_targets:
        results.append("⚠️ No source targets discovered for unit test generation")

    for target in unit_test_targets:
        gen_result = await generate_unit_tests(repo_path=repo_path, target_file=target)
        if "✅" in gen_result:
            generated_count += 1
            artifact = _extract_generated_artifact(repo_path, gen_result)
            if artifact:
                generated_artifacts.append(artifact)
        results.append(f"\n📝 Target: {target}")
        results.append(gen_result[:300])

    if base_url.strip():
        e2e_result = await generate_e2e_tests(repo_path=repo_path, base_url=base_url, test_name="media_tracker")
        results.extend(["\n🌐 E2E Tests:", e2e_result])
        if "✅" in e2e_result:
            generated_count += 1
            artifact = _extract_generated_artifact(repo_path, e2e_result)
            if artifact:
                generated_artifacts.append(artifact)

    results.extend(["\n" + "=" * 70, "👤 AGENT 4: EXECUTOR AGENT", "=" * 70])
    logger.info("Orchestration: starting executor agent")
    exec_result = await execute_tests(repo_path=repo_path)
    results.append(exec_result)

    if "failed" in exec_result.lower() or "❌" in exec_result:
        results.extend(["\n" + "=" * 70, "👤 AGENT 5: REPAIRER AGENT", "=" * 70])
        logger.info("Orchestration: starting repair agent due to failures")
        results.append(await repair_failing_tests(repo_path=repo_path, test_output=exec_result))
    else:
        results.append("\n⏭️  Agent 5 (Repairer) skipped - no failures detected")

    results.extend(["\n" + "=" * 70, "👤 AGENT 6: CI/CD AGENT", "=" * 70])
    logger.info("Orchestration: starting CI/CD agent")
    workflow_result = await generate_github_workflow(repo_path=repo_path, test_command="pytest --cov=backend --cov-report=xml -v")
    results.append(workflow_result)

    workflow_artifact = _extract_generated_artifact(repo_path, workflow_result)
    if workflow_artifact:
        generated_artifacts.append(workflow_artifact)

    if generated_artifacts:
        results.extend(["\n" + "=" * 70, "👤 AGENT 7: GITHUB PR AGENT", "=" * 70])
        logger.info("Orchestration: starting github PR agent")
        fixes = []
        for artifact in generated_artifacts:
            artifact_path = Path(repo_path) / artifact.relative_path
            fixes.append(
                {
                    "file": artifact.relative_path,
                    "content": artifact_path.read_text(encoding="utf-8"),
                    "description": artifact.description,
                }
            )
        pr_result = await create_test_fix_pr(repo_url=repo_url, test_output=exec_result, fixes=json.dumps(fixes))
        results.append(pr_result)
    else:
        results.append("\n⏭️  Agent 7 (GitHub PR) skipped - no generated artifacts available")

    results.extend(
        [
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
  {"✅ GitHub PR Agent - Test PR created" if generated_artifacts else "⏭️  GitHub PR Agent - Skipped (no generated artifacts)"}
""",
        ]
    )

    logger.info("Orchestration complete for repo_path=%s", repo_path)
    return "\n".join(results)


if __name__ == "__main__":
    logger.info("Starting Autonomous QA Testing Council MCP server...")
    logger.info("Workspace directory: %s", WORKSPACE_DIR)
    logger.info("Test results directory: %s", TEST_RESULTS_DIR)
    logger.info("Coverage directory: %s", COVERAGE_DIR)
    mcp.run(transport="stdio")
