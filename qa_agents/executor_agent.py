"""Executor agent for running discovered test commands and summarizing results."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .audit_schema import FailurePayload
from .utils import verify_path_exists

logger = logging.getLogger("qa-council-server.executor-agent")


@dataclass(frozen=True)
class TestCommand:
    """Concrete command invocation for a test runner."""

    kind: str
    cmd: list[str]
    fallback_cmd: list[str] | None = None
    report_file: str = "N/A"
    coverage_file: str = "N/A"


def _load_package_json(repo: Path) -> dict:
    package_json = repo / "package.json"
    if not package_json.exists():
        return {}
    try:
        return json.loads(package_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _discover_test_command(repo: Path, test_results_dir: Path, coverage_dir: Path, test_path: str = "") -> TestCommand:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = test_results_dir / f"report_{timestamp}.html"
    coverage_file = coverage_dir / f"coverage_{timestamp}.xml"
    package_json = _load_package_json(repo)
    deps = {**package_json.get("dependencies", {}), **package_json.get("devDependencies", {})}

    pytest_markers = [repo / "pytest.ini", repo / "pyproject.toml", repo / "tox.ini"]
    has_pytest_markers = any(marker.exists() for marker in pytest_markers)
    has_python_tests = any(repo.glob("tests/**/*.py")) or any(repo.glob("test_*.py"))

    if has_pytest_markers or has_python_tests:
        return TestCommand(
            kind="pytest",
            cmd=[
                "pytest",
                "-v",
                "--tb=short",
                f"--html={report_file}",
                "--self-contained-html",
                f"--cov={test_path or str(repo)}",
                f"--cov-report=xml:{coverage_file}",
                "--cov-report=term",
                test_path or str(repo),
            ],
            fallback_cmd=["pytest", "-v", "--tb=short", test_path or str(repo)],
            report_file=str(report_file),
            coverage_file=str(coverage_file),
        )

    if (repo / "package.json").exists() and "vitest" in deps:
        return TestCommand(kind="vitest", cmd=["npm", "run", "test", "--", "--run"], fallback_cmd=["npm", "test"])

    if (repo / "package.json").exists() and "jest" in deps:
        return TestCommand(kind="jest", cmd=["npm", "test", "--", "--runInBand"], fallback_cmd=["npm", "test"])

    if has_python_tests or any(repo.rglob("*.py")):
        return TestCommand(kind="unittest", cmd=["python", "-m", "unittest", "discover", "-v", test_path or "tests"])

    return TestCommand(kind="default", cmd=["pytest", "-v", "--tb=short", test_path or str(repo)])


def _extract_test_summary(output: str) -> tuple[int, int, int, bool]:
    patterns = [
        r"(?:(\d+) passed)?(?:,\s*)?(?:(\d+) failed)?(?:,\s*)?(?:(\d+) skipped)?(?:,\s*)?in\s",
        r"Tests:\s*(?:\d+\s+total,\s*)?(?:(\d+) passed)?(?:,\s*)?(?:(\d+) failed)?(?:,\s*)?(?:(\d+) skipped)?",
    ]
    passed = failed = skipped = 0
    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            passed = int((match.group(1) or "0"))
            failed = int((match.group(2) or "0"))
            skipped = int((match.group(3) or "0"))
            break

    lowered = output.lower()
    no_tests_collected = any(marker in lowered for marker in ("no tests ran", "collected 0 items", "no test files found", "0 passing"))
    return passed, failed, skipped, no_tests_collected


def _extract_coverage_pct(output: str) -> str:
    for pattern in (r"TOTAL\s+\d+\s+\d+\s+(\d+)%", r"coverage[:\s]+(\d+(?:\.\d+)?)%"):
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return "N/A"


def _run_command(cmd: list[str], cwd: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _extract_failure_payloads(output: str) -> list[FailurePayload]:
    payloads: list[FailurePayload] = []
    if "timeout" in output.lower():
        selector_match = re.search(r"(#[-_a-zA-Z0-9]+|\.[-_a-zA-Z0-9]+)", output)
        selector = selector_match.group(1) if selector_match else "#submit-btn"
        dom_snapshot = "<html><body><button id='submit-button'>Submit</button></body></html>"
        payloads.append(FailurePayload(error="Timeout", selector=selector, dom_snapshot=dom_snapshot, traceback=output[:500]))
    elif re.search(r"AssertionError|Traceback", output):
        payloads.append(FailurePayload(error="AssertionError", selector="#unknown", dom_snapshot="<html></html>", traceback=output[:500]))
    return payloads


def _persist_loguru_trace(test_results_dir: Path, result: dict, failure_payloads: list[FailurePayload]) -> str:
    trace_file = test_results_dir / f"loguru_trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    structured = {
        "runner": result.get("runner", "unknown"),
        "exit_code": result.get("exit_code", 1),
        "stdout": result.get("stdout", "")[:3000],
        "stderr": result.get("stderr", "")[:3000],
        "failure_payloads": [item.__dict__ for item in failure_payloads],
    }
    trace_file.write_text(json.dumps(structured, indent=2), encoding="utf-8")
    return str(trace_file)


def _run_tests(repo_path: str, test_results_dir: Path, coverage_dir: Path, test_path: str = "") -> tuple[bool, dict]:
    test_results_dir.mkdir(parents=True, exist_ok=True)
    coverage_dir.mkdir(parents=True, exist_ok=True)

    repo = Path(repo_path)
    selected = _discover_test_command(repo, test_results_dir, coverage_dir, test_path)
    logger.info("Executing %s command: %s", selected.kind, " ".join(selected.cmd))

    try:
        primary = _run_command(selected.cmd, repo_path)
        combined = f"{primary.stdout}\n{primary.stderr}"

        plugin_option_error = "unrecognized arguments:" in combined or "Unknown option" in combined
        if primary.returncode != 0 and plugin_option_error and selected.fallback_cmd:
            fallback = _run_command(selected.fallback_cmd, repo_path)
            return True, {
                "runner": selected.kind,
                "exit_code": fallback.returncode,
                "stdout": fallback.stdout,
                "stderr": fallback.stderr,
                "report_file": "N/A (fallback mode)",
                "coverage_file": "N/A (fallback mode)",
                "used_fallback": True,
            }

        return True, {
            "runner": selected.kind,
            "exit_code": primary.returncode,
            "stdout": primary.stdout,
            "stderr": primary.stderr,
            "report_file": selected.report_file,
            "coverage_file": selected.coverage_file,
            "used_fallback": False,
        }
    except subprocess.TimeoutExpired:
        return False, {"error": "Test execution timed out"}
    except FileNotFoundError as cmd_error:
        return False, {"error": f"Missing test command: {cmd_error}"}


async def execute_tests(repo_path: str, test_results_dir: Path, coverage_dir: Path, test_path: str = "") -> str:
    """Execute discovered tests and summarize outcomes."""
    if not repo_path.strip():
        return "❌ Error: Repository path is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        return f"❌ Error: {verified_path}"

    success, result = _run_tests(verified_path, test_results_dir, coverage_dir, test_path)
    if not success:
        return f"❌ Test execution error: {result.get('error', 'Unknown error')}"

    combined_output = f"{result.get('stdout', '')}\n{result.get('stderr', '')}".strip()
    passed, failed, skipped, no_tests_collected = _extract_test_summary(combined_output)
    coverage_pct = _extract_coverage_pct(combined_output)
    failure_payloads = _extract_failure_payloads(combined_output)
    trace_file = _persist_loguru_trace(test_results_dir, result, failure_payloads)

    status = "✅" if result.get("exit_code", 1) == 0 and not no_tests_collected else "❌" if result.get("exit_code", 1) != 0 else "⚠️"
    failure_json = json.dumps([p.__dict__ for p in failure_payloads], indent=2)

    return f"""{status} Test Execution Complete

📊 Results:
- Runner: {result.get('runner', 'unknown')}
- Passed: {passed}
- Failed: {failed}
- Skipped: {skipped}
- Coverage: {coverage_pct}%
- No tests collected: {no_tests_collected}

📄 Report: {result.get('report_file')}
📈 Coverage: {result.get('coverage_file')}
🧾 Loguru JSON Trace: {trace_file}

FailurePayload:
{failure_json}

{combined_output[:1600]}
"""
