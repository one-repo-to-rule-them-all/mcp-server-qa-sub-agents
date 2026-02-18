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

    fallback_cmd = ["pytest", "-v", "--tb=short", test_path or repo_path]

    try:
        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=300)
        combined_output = f"{result.stdout}\n{result.stderr}"

        if "unrecognized arguments:" in combined_output:
            logger.warning(
                "Pytest options unsupported in current environment; retrying with fallback command: %s",
                " ".join(fallback_cmd),
            )
            fallback_result = subprocess.run(fallback_cmd, cwd=repo_path, capture_output=True, text=True, timeout=300)
            logger.info("Fallback pytest finished with exit code %s", fallback_result.returncode)
            return True, {
                "exit_code": fallback_result.returncode,
                "stdout": fallback_result.stdout,
                "stderr": fallback_result.stderr,
                "report_file": "N/A (pytest-html plugin unavailable)",
                "coverage_file": "N/A (pytest-cov plugin unavailable)",
                "used_fallback": True,
            }

        logger.info("Pytest finished with exit code %s", result.returncode)
        return True, {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "report_file": str(report_file),
            "coverage_file": str(coverage_file),
            "used_fallback": False,
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
    stderr = result.get("stderr", "")
    combined_output = f"{stdout}\n{stderr}".strip()

    summary_match = re.search(
        r"=+\s*(?:(\d+) passed)?(?:,\s*)?(?:(\d+) failed)?(?:,\s*)?(?:(\d+) skipped)?(?:,\s*)?in\s",
        combined_output,
    )
    passed = int(summary_match.group(1) or 0) if summary_match else combined_output.count(" passed")
    failed = int(summary_match.group(2) or 0) if summary_match else combined_output.count(" failed")
    skipped = int(summary_match.group(3) or 0) if summary_match else combined_output.count(" skipped")
    no_tests_collected = "no tests ran" in combined_output.lower() or "collected 0 items" in combined_output.lower()

    coverage_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", combined_output)
    coverage_pct = coverage_match.group(1) if coverage_match else "N/A"

    exit_code = result.get("exit_code", 1)
    has_pytest_errors = bool(re.search(r"(ERRORS?|usage: pytest|ImportError|ModuleNotFoundError)", combined_output))
    if exit_code != 0 and failed == 0 and has_pytest_errors:
        failed = 1

    logger.info(
        "Execution summary: passed=%d failed=%d skipped=%d coverage=%s no_tests=%s exit_code=%s",
        passed,
        failed,
        skipped,
        coverage_pct,
        no_tests_collected,
        exit_code,
    )

    status = "✅" if exit_code == 0 and not no_tests_collected else "❌" if exit_code != 0 else "⚠️"
    fallback_note = "\n⚠️ Fallback mode used (pytest-html/pytest-cov options unavailable).\n" if result.get("used_fallback") else ""
    return f"""{status} Test Execution Complete

📊 Results:
- Passed: {passed}
- Failed: {failed}
- Skipped: {skipped}
- Coverage: {coverage_pct}%
- No tests collected: {no_tests_collected}

📄 Report: {result.get('report_file')}
📈 Coverage: {result.get('coverage_file')}
{fallback_note}

{combined_output[:2000]}
"""
