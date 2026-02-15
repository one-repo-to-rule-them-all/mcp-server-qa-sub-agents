"""Executor agent for running pytest and summarizing results."""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path

from .utils import verify_path_exists

logger = logging.getLogger("qa-council-server.executor-agent")


def _run_pytest(repo_path: str, test_results_dir: Path, coverage_dir: Path, test_path: str = "") -> tuple[bool, dict]:
    """Run pytest and collect key report paths for downstream agent summaries."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = test_results_dir / f"report_{timestamp}.html"
    coverage_file = coverage_dir / f"coverage_{timestamp}.xml"

    cmd = [
        "pytest",
        "-v",
        "--tb=short",
        f"--html={report_file}",
        "--self-contained-html",
        f"--cov={repo_path}",
        f"--cov-report=xml:{coverage_file}",
        "--cov-report=term",
        test_path or repo_path,
    ]
    logger.info("Executing pytest command: %s", " ".join(cmd))

    try:
        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=300)
        logger.info("Pytest finished with exit code %s", result.returncode)
        return True, {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "report_file": str(report_file),
            "coverage_file": str(coverage_file),
        }
    except subprocess.TimeoutExpired:
        logger.error("Pytest execution timed out after 300 seconds")
        return False, {"error": "Test execution timed out"}


async def execute_tests(repo_path: str, test_results_dir: Path, coverage_dir: Path, test_path: str = "") -> str:
    """Execute pytest tests with coverage reporting."""
    logger.info("Starting test execution: repo_path=%s, test_path=%s", repo_path, test_path or "<all>")

    if not repo_path.strip():
        logger.warning("Test execution aborted: repository path was empty")
        return "❌ Error: Repository path is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        logger.warning("Test execution aborted: invalid repository path (%s)", verified_path)
        return f"❌ Error: {verified_path}"

    success, result = _run_pytest(verified_path, test_results_dir, coverage_dir, test_path)
    if not success:
        return f"❌ Test execution error: {result.get('error', 'Unknown error')}"

    stdout = result.get("stdout", "")
    passed = stdout.count(" passed")
    failed = stdout.count(" failed")
    coverage_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", stdout)
    coverage_pct = coverage_match.group(1) if coverage_match else "N/A"

    logger.info("Execution summary: passed=%d failed=%d coverage=%s", passed, failed, coverage_pct)

    status = "✅" if result.get("exit_code", 1) == 0 else "⚠️"
    return f"""{status} Test Execution Complete

📊 Results:
- Passed: {passed}
- Failed: {failed}
- Coverage: {coverage_pct}%

📄 Report: {result.get('report_file')}
📈 Coverage: {result.get('coverage_file')}

{stdout[:2000]}
"""
