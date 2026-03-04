#!/usr/bin/env python3
"""Autonomous QA Testing Council MCP Server."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from qa_agents.analyzer_agent import (
    analyze_codebase as analyzer_agent_analyze_codebase,
)
from qa_agents.analyzer_agent import discover_tech_stack_manifest, discover_testable_surfaces, discover_unit_test_targets
from qa_agents.audit_schema import AuditTrail, FailurePayload
from qa_agents.cicd_agent import generate_github_workflow as cicd_agent_generate_github_workflow
from qa_agents.executor_agent import execute_tests as executor_agent_execute_tests
from qa_agents.generator_agent import generate_e2e_tests as generator_agent_generate_e2e_tests
from qa_agents.generator_agent import generate_integration_tests as generator_agent_generate_integration_tests
from qa_agents.generator_agent import generate_unit_tests as generator_agent_generate_unit_tests
from qa_agents.github_pr_agent import create_test_fix_pr as github_agent_create_test_fix_pr
from qa_agents.repair_agent import repair_failing_tests as repair_agent_repair_failing_tests
from qa_agents.repository_agent import clone_repository as repository_agent_clone_repository
from qa_agents.utils import configure_json_logging, get_directory_from_env

import logging

configure_json_logging()
logger = logging.getLogger("qa-council-server")

mcp = FastMCP("qa-council")

WORKSPACE_DIR = get_directory_from_env("WORKSPACE_DIR", "/app/repos")
TEST_RESULTS_DIR = get_directory_from_env("TEST_RESULTS_DIR", "/app/test_results")
COVERAGE_DIR = get_directory_from_env("COVERAGE_DIR", "/app/coverage")
SESSION_CONTEXT_FILE = WORKSPACE_DIR / "session_context.json"


@dataclass
class GeneratedArtifact:
    relative_path: str
    description: str


def _extract_generated_artifact(repo_path: str, generator_output: str) -> GeneratedArtifact | None:
    match = re.search(r"(?:📝 Test file|📄 Workflow file):\s*(.+)", generator_output)
    if not match:
        return None
    generated_path = Path(match.group(1).strip())
    if not generated_path.exists():
        return None
    try:
        relative_path = str(generated_path.relative_to(Path(repo_path)))
    except ValueError:
        return None
    return GeneratedArtifact(relative_path=relative_path, description=f"Generated QA artifact for {relative_path}")


def _load_context() -> dict:
    if not SESSION_CONTEXT_FILE.exists():
        return {}
    try:
        return json.loads(SESSION_CONTEXT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_context(context: dict) -> None:
    SESSION_CONTEXT_FILE.write_text(json.dumps(context, indent=2), encoding="utf-8")


def _extract_failure_payloads(executor_output: str) -> list[FailurePayload]:
    match = re.search(r"FailurePayload:\n(\[.*?\])\n\n", executor_output, re.DOTALL)
    if not match:
        return []
    try:
        return [FailurePayload(**payload) for payload in json.loads(match.group(1))]
    except Exception:
        return []


@mcp.tool()
async def list_tools() -> str:
    """Expose tool list for inter-agent communication."""
    return json.dumps(
        {
            "tools": [
                "clone_repository",
                "analyze_codebase",
                "generate_unit_tests",
                "generate_integration_tests",
                "generate_e2e_tests",
                "execute_tests",
                "repair_failing_tests",
                "generate_github_workflow",
                "create_test_fix_pr",
                "orchestrate_full_qa_cycle",
                "call_tool",
            ]
        },
        indent=2,
    )


@mcp.tool()
async def call_tool(tool_name: str, payload: str = "{}") -> str:
    """Simple inter-agent dispatcher for MCP council tooling."""
    args = json.loads(payload or "{}")
    dispatch = {
        "clone_repository": clone_repository,
        "analyze_codebase": analyze_codebase,
        "generate_unit_tests": generate_unit_tests,
        "generate_integration_tests": generate_integration_tests,
        "generate_e2e_tests": generate_e2e_tests,
        "execute_tests": execute_tests,
        "repair_failing_tests": repair_failing_tests,
        "generate_github_workflow": generate_github_workflow,
        "create_test_fix_pr": create_test_fix_pr,
        "orchestrate_full_qa_cycle": orchestrate_full_qa_cycle,
    }
    if tool_name not in dispatch:
        return f"❌ Unknown tool: {tool_name}"
    return await dispatch[tool_name](**args)


@mcp.tool()
async def clone_repository(repo_url: str = "", branch: str = "main") -> str:
    return await repository_agent_clone_repository(repo_url, branch, WORKSPACE_DIR)


@mcp.tool()
async def analyze_codebase(repo_path: str = "", file_pattern: str = "*.py") -> str:
    return await analyzer_agent_analyze_codebase(repo_path, file_pattern)


@mcp.tool()
async def generate_unit_tests(repo_path: str = "", target_file: str = "", manifest_json: str = "") -> str:
    return await generator_agent_generate_unit_tests(repo_path, target_file, manifest_json)


@mcp.tool()
async def generate_integration_tests(repo_path: str = "", service_name: str = "service", manifest_json: str = "") -> str:
    return await generator_agent_generate_integration_tests(repo_path, service_name, manifest_json)


@mcp.tool()
async def generate_e2e_tests(repo_path: str = "", base_url: str = "", test_name: str = "app", manifest_json: str = "") -> str:
    return await generator_agent_generate_e2e_tests(repo_path, base_url, test_name, manifest_json)


@mcp.tool()
async def execute_tests(repo_path: str = "", test_path: str = "") -> str:
    return await executor_agent_execute_tests(repo_path, TEST_RESULTS_DIR, COVERAGE_DIR, test_path)


@mcp.tool()
async def repair_failing_tests(repo_path: str = "", test_output: str = "") -> str:
    return await repair_agent_repair_failing_tests(repo_path, test_output)


@mcp.tool()
async def generate_github_workflow(
    repo_path: str = "",
    test_command: str = "pytest",
    trigger_workflow: str = "true",
    workflow_repo: str = "one-repo-to-rule-them-all/media-collection-tracker",
    workflow_ref: str = "main",
) -> str:
    return await cicd_agent_generate_github_workflow(
        repo_path=repo_path,
        test_command=test_command,
        trigger_workflow=trigger_workflow,
        workflow_repo=workflow_repo,
        workflow_ref=workflow_ref,
    )


@mcp.tool()
async def create_test_fix_pr(repo_url: str = "", test_output: str = "", fixes: str = "") -> str:
    return await github_agent_create_test_fix_pr(repo_url, test_output, fixes, WORKSPACE_DIR)


@mcp.tool()
async def orchestrate_full_qa_cycle(repo_url: str = "", branch: str = "main", base_url: str = "") -> str:
    """Orchestrator controlling a 7-agent AuditTrail pipeline and persistence."""
    if not repo_url.strip():
        return "❌ Error: Repository URL is required"

    session_id = str(uuid.uuid4())
    audit = AuditTrail(session_id=session_id, repo_url=repo_url, branch=branch)
    results: list[str] = []

    clone_result = await clone_repository(repo_url=repo_url, branch=branch)
    results.append(clone_result)
    if "❌" in clone_result:
        return "\n".join(results)

    repo_path = clone_result.split(": ", 1)[1] if ": " in clone_result else ""
    audit.repo_path = repo_path

    repo = Path(repo_path)
    manifest = discover_tech_stack_manifest(repo)
    audit.manifest = manifest
    surfaces = discover_testable_surfaces(repo)
    audit.testable_surfaces = surfaces

    results.append("\nAgent 2 Inspector Manifest:\n" + json.dumps(manifest.__dict__, indent=2))
    results.append("\nAgent 3 Analyst Surfaces:\n" + json.dumps(surfaces, indent=2))

    generated_artifacts: list[GeneratedArtifact] = []
    for target in discover_unit_test_targets(repo):
        gen_result = await generate_unit_tests(repo_path=repo_path, target_file=target, manifest_json=json.dumps(manifest.__dict__))
        results.append(gen_result)
        artifact = _extract_generated_artifact(repo_path, gen_result)
        if artifact:
            generated_artifacts.append(artifact)
            audit.generated_artifacts.append({"file": artifact.relative_path, "description": artifact.description})

    integration_result = await generate_integration_tests(repo_path=repo_path, service_name="api", manifest_json=json.dumps(manifest.__dict__))
    results.append(integration_result)
    artifact = _extract_generated_artifact(repo_path, integration_result)
    if artifact:
        generated_artifacts.append(artifact)

    if base_url.strip():
        e2e_result = await generate_e2e_tests(repo_path=repo_path, base_url=base_url, test_name="council", manifest_json=json.dumps(manifest.__dict__))
        results.append(e2e_result)
        artifact = _extract_generated_artifact(repo_path, e2e_result)
        if artifact:
            generated_artifacts.append(artifact)

    exec_result = await execute_tests(repo_path=repo_path)
    results.append(exec_result)
    audit.executor_results = {"raw": exec_result}
    failures = _extract_failure_payloads(exec_result)
    audit.failure_payloads = failures

    if failures:
        heal_result = await repair_failing_tests(repo_path=repo_path, test_output=exec_result)
        results.append(heal_result)
        audit.repair_logs.append(heal_result)
        verification_result = await execute_tests(repo_path=repo_path)
        results.append("\nVerification Run:\n" + verification_result)

    workflow_result = await generate_github_workflow(repo_path=repo_path, test_command="pytest -v")
    results.append(workflow_result)

    workflow_artifact = _extract_generated_artifact(repo_path, workflow_result)
    if workflow_artifact:
        generated_artifacts.append(workflow_artifact)

    quality_gate = {
        "generated_files": len(generated_artifacts),
        "healed_failures": len(audit.failure_payloads),
        "manifest": manifest.__dict__,
    }
    audit.quality_gate_report = quality_gate

    context = _load_context()
    context[session_id] = audit.to_dict()
    _save_context(context)

    if generated_artifacts:
        fixes = []
        for artifact in generated_artifacts:
            artifact_path = Path(repo_path) / artifact.relative_path
            if artifact_path.exists():
                fixes.append({"file": artifact.relative_path, "content": artifact_path.read_text(encoding="utf-8"), "description": artifact.description})
        pr_result = await create_test_fix_pr(repo_url=repo_url, test_output=exec_result, fixes=json.dumps(fixes))
        results.append(pr_result)

    results.append("\nFinal Quality Gate:\n" + json.dumps(quality_gate, indent=2))
    return "\n".join(results)


if __name__ == "__main__":
    logger.info("Starting Autonomous QA Testing Council MCP server")
    mcp.run(transport="stdio")
