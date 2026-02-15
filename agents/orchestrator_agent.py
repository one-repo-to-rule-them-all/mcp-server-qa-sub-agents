"""Orchestrator Agent: coordinates the full QA lifecycle.

Dynamically discovers test targets from analyzer output instead of
hardcoding file paths.  Pure coordination — no business logic.

Pipeline:
    Repository → Analyzer → Target Selection → Generator → Executor
    → (optional) Repair → CI/CD → Aggregate Results
"""
import os
from datetime import datetime

from utils.config import get_logger

logger = get_logger("orchestrator")


# ── Dynamic Target Selection ─────────────────────────────────────────────

# Files/patterns that should never be selected for test generation.
EXCLUDE_PATTERNS = {
    "__init__", "conftest", "setup", "manage", "wsgi", "asgi",
    "alembic", "migration", "version", "celeryconfig",
}
EXCLUDE_PREFIXES = ("test_", "tests_")
EXCLUDE_DIRS = {"migrations", "alembic", "versions", "__pycache__"}


def select_test_targets(analyses: list[dict], max_targets: int = 10) -> list[dict]:
    """Score and rank files by testability, returning the best targets.

    Scoring:
        +2  per public function
        +3  per class
        +1  per complexity indicator (file_io, subprocess, http, etc.)

    Args:
        analyses: List of per-file analysis dicts from analyzer agent.
        max_targets: Maximum number of files to return.

    Returns:
        Sorted list of analysis dicts (highest score first).
    """
    scored: list[tuple[float, dict]] = []

    for data in analyses:
        if data.get("error"):
            continue

        module = data.get("module", "")
        filepath = data.get("filepath", "")

        # Exclude non-target files
        if module.lower() in EXCLUDE_PATTERNS:
            continue
        if any(module.lower().startswith(p) for p in EXCLUDE_PREFIXES):
            continue
        # Check if file is inside an excluded directory
        parts = filepath.replace("\\", "/").split("/")
        if any(p in EXCLUDE_DIRS for p in parts):
            continue

        functions = data.get("functions", [])
        classes = data.get("classes", [])

        if not functions and not classes:
            continue

        # Calculate score
        score = 0.0
        score += len(functions) * 2
        score += len(classes) * 3

        # Complexity bonus
        for fn in functions:
            cx = fn.get("complexity_indicators", {})
            score += sum(1 for v in cx.values() if v)

        for cls in classes:
            for method in cls.get("methods", []):
                cx = method.get("complexity_indicators", {})
                score += sum(0.5 for v in cx.values() if v)

        scored.append((score, data))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    return [data for _, data in scored[:max_targets]]


# ── Orchestration ────────────────────────────────────────────────────────


async def orchestrate_full_qa_cycle(
    repo_url: str = "",
    branch: str = "main",
    base_url: str = "http://localhost:8000",
) -> str:
    """Run the full QA pipeline: clone → analyze → generate → execute → report.

    Args:
        repo_url: GitHub repository URL to test.
        branch: Git branch to checkout.
        base_url: Application URL for E2E tests (if applicable).

    Returns:
        Aggregated status report from all agents.
    """
    if not repo_url.strip():
        return "Error: Repository URL is required"

    # Lazy imports to avoid circular dependencies at module level
    from agents.repository_agent import clone_repository
    from agents.analyzer_agent import run_analysis
    from agents.generator_agent import run_unit_test_generation, run_e2e_test_generation
    from agents.executor_agent import run_test_execution
    from agents.repair_agent import run_repair_analysis
    from agents.cicd_agent import run_workflow_generation

    start = datetime.now()
    results: list[str] = []
    results.append(f"QA Council Orchestration Started at {start.strftime('%H:%M:%S')}")
    results.append(f"Repository: {repo_url}")
    results.append(f"Branch: {branch}")
    results.append("=" * 60)

    # ── Phase 1: Clone Repository ─────────────────────────────────────
    logger.info("Phase 1: Cloning repository")
    results.append("\n[Phase 1] Repository Setup")
    clone_result = await clone_repository(repo_url, branch)
    results.append(f"  {clone_result}")

    if "failed" in clone_result.lower() or "error" in clone_result.lower():
        results.append("\nOrchestration aborted: repository clone failed.")
        return "\n".join(results)

    # Extract repo path from clone result
    repo_path = clone_result.replace("Repository ready at: ", "").strip()

    # ── Phase 2: Analyze Codebase ─────────────────────────────────────
    logger.info("Phase 2: Analyzing codebase")
    results.append("\n[Phase 2] Code Analysis")
    analysis_report, raw_analyses = await run_analysis(repo_path)
    results.append(f"  {analysis_report.split(chr(10))[0]}")  # First line summary

    if not raw_analyses:
        results.append("\nOrchestration aborted: analysis found no Python files.")
        return "\n".join(results)

    # ── Phase 3: Select Targets ───────────────────────────────────────
    logger.info("Phase 3: Selecting test targets")
    results.append("\n[Phase 3] Target Selection")
    targets = select_test_targets(raw_analyses)
    target_names = [t.get("module", "unknown") for t in targets]
    results.append(f"  Selected {len(targets)} files for test generation:")
    for name in target_names:
        results.append(f"    - {name}")

    # ── Phase 4: Generate Tests ───────────────────────────────────────
    logger.info("Phase 4: Generating tests")
    results.append("\n[Phase 4] Test Generation")

    # Generate unit tests for each target
    for target in targets:
        filepath = target.get("filepath", "")
        if filepath:
            gen_result = await run_unit_test_generation(
                repo_path=repo_path, target_file=filepath
            )
            # Extract just the summary line
            first_line = gen_result.split("\n")[0]
            results.append(f"  {target.get('module', '?')}: {first_line}")

    # Generate E2E tests if base_url is provided
    if base_url:
        e2e_result = await run_e2e_test_generation(
            repo_path=repo_path, base_url=base_url
        )
        results.append(f"  E2E: {e2e_result.split(chr(10))[0]}")

    # ── Phase 5: Execute Tests ────────────────────────────────────────
    logger.info("Phase 5: Executing tests")
    results.append("\n[Phase 5] Test Execution")

    test_dir = os.path.join(repo_path, "tests", "generated")
    exec_result = await run_test_execution(
        repo_path=repo_path, test_path=test_dir
    )
    results.append(f"  {exec_result.split(chr(10))[0]}")

    # ── Phase 6: Repair Analysis (if failures) ────────────────────────
    if "failed" in exec_result.lower() or "error" in exec_result.lower():
        logger.info("Phase 6: Running repair analysis")
        results.append("\n[Phase 6] Repair Analysis")
        repair_result = await run_repair_analysis(
            repo_path=repo_path, test_output=exec_result
        )
        results.append(f"  {repair_result.split(chr(10))[0]}")
    else:
        results.append("\n[Phase 6] Repair Analysis — Skipped (no failures)")

    # ── Phase 7: CI/CD Workflow ───────────────────────────────────────
    logger.info("Phase 7: Generating CI/CD workflow")
    results.append("\n[Phase 7] CI/CD Workflow Generation")
    workflow_result = await run_workflow_generation(repo_path=repo_path)
    results.append(f"  {workflow_result.split(chr(10))[0]}")

    # ── Summary ───────────────────────────────────────────────────────
    elapsed = (datetime.now() - start).total_seconds()
    results.append("\n" + "=" * 60)
    results.append(f"QA Council Orchestration Complete")
    results.append(f"Duration: {elapsed:.1f}s")
    results.append(f"Files analyzed: {len(raw_analyses)}")
    results.append(f"Test targets: {len(targets)}")
    results.append(f"Phases completed: 7")

    return "\n".join(results)
