"""Executor Agent: run tests and collect metrics.

Responsible for executing pytest test suites, collecting coverage data,
and generating test reports with timing and pass/fail statistics.
"""
import re
import subprocess
from pathlib import Path
from datetime import datetime

from utils.config import TEST_RESULTS_DIR, COVERAGE_DIR, get_logger
from utils.path_utils import verify_path_exists

logger = get_logger("executor")


def run_pytest(repo_path: str, test_path: str = "") -> tuple:
    """Execute pytest with coverage reporting.

    Args:
        repo_path: Root path of the repository
        test_path: Specific test file or directory to run (optional)

    Returns:
        Tuple of (success: bool, result_dict: dict)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = TEST_RESULTS_DIR / f"report_{timestamp}.html"
    coverage_file = COVERAGE_DIR / f"coverage_{timestamp}.xml"

    cmd = [
        "pytest", "-v", "--tb=short",
        f"--html={report_file}", "--self-contained-html",
        f"--cov={repo_path}",
        f"--cov-report=xml:{coverage_file}",
        "--cov-report=term"
    ]

    if test_path:
        cmd.append(test_path)
    else:
        cmd.append(repo_path)

    try:
        result = subprocess.run(
            cmd, cwd=repo_path,
            capture_output=True, text=True, timeout=300
        )
        return True, {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "report_file": str(report_file),
            "coverage_file": str(coverage_file)
        }
    except subprocess.TimeoutExpired:
        return False, {"error": "Test execution timed out (5 min limit)"}
    except Exception as e:
        return False, {"error": str(e)}


async def run_test_execution(repo_path: str = "", test_path: str = "") -> str:
    """Execute pytest tests with coverage reporting.

    Args:
        repo_path: Root path of the repository
        test_path: Specific test file or directory (optional)

    Returns:
        Formatted string with test results, coverage, and report paths.
    """
    if not repo_path.strip():
        return "Error: Repository path is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        return f"Error: {verified_path}"

    logger.info(f"Executing tests in: {verified_path}")

    success, result = run_pytest(verified_path, test_path)

    if not success:
        return f"Test execution error: {result.get('error', 'Unknown error')}"

    exit_code = result.get("exit_code", 1)
    stdout = result.get("stdout", "")

    passed = stdout.count(" passed")
    failed = stdout.count(" failed")

    coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', stdout)
    coverage_pct = coverage_match.group(1) if coverage_match else "N/A"

    status = "PASS" if exit_code == 0 else "WARN"

    return f"""{status} Test Execution Complete

Results:
- Passed: {passed}
- Failed: {failed}
- Coverage: {coverage_pct}%

Report: {result.get('report_file')}
Coverage: {result.get('coverage_file')}

{stdout[:2000]}
"""
