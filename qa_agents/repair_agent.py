"""Repair agent.

Parses failed test output and returns actionable remediation suggestions.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("qa-council-server.repair-agent")


def _parse_test_failures(pytest_output: str) -> list[dict]:
    """Parse pytest console output and extract per-test failure blocks."""
    failures = []
    lines = pytest_output.split("\n")
    current_failure = {}
    in_failure = False

    # Track contiguous failure blocks emitted by pytest.
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("FAILED") or " FAILED" in stripped:
            in_failure = True
            test_name = stripped.split()[0]
            if "::" in stripped:
                test_name = stripped.split()[0]
            current_failure = {"test": test_name, "lines": [stripped]}
        elif in_failure:
            if stripped.startswith(("===", "PASSED", "FAILED")):
                if current_failure.get("lines"):
                    failures.append(current_failure)
                current_failure = {}
                in_failure = False
            else:
                current_failure.setdefault("lines", []).append(stripped)

    if current_failure.get("lines"):
        failures.append(current_failure)

    if failures:
        return failures

    lowered = pytest_output.lower()
    if "usage: pytest" in lowered or "unrecognized arguments:" in lowered:
        return [{"test": "pytest invocation error", "lines": ["Pytest command includes unsupported options/plugins"]}]
    if "importerror" in lowered or "modulenotfounderror" in lowered:
        return [{"test": "test environment import error", "lines": ["One or more modules could not be imported"]}]

    return failures


def _generate_test_repair(failure_info: dict) -> list[str]:
    """Generate actionable heuristics from parsed failure text."""
    suggestions = []
    failure_text = "\n".join(failure_info.get("lines", []))

    if "AssertionError" in failure_text:
        suggestions.append("Check assertion conditions - expected vs actual values may not match")
    if "AttributeError" in failure_text:
        suggestions.append("Verify object attributes and method names are correct")
    if "TypeError" in failure_text:
        suggestions.append("Check function argument types and counts")
    if "ImportError" in failure_text or "ModuleNotFoundError" in failure_text:
        suggestions.append("Ensure all required modules are installed and import paths are correct")
    if "fixture" in failure_text.lower():
        suggestions.append("Verify pytest fixtures are properly defined and scoped")
    if "unsupported options/plugins" in failure_text:
        suggestions.append("Install pytest plugins used by the command (e.g., pytest-cov, pytest-html)")
        suggestions.append("Or rerun pytest without --cov/--html flags when plugins are unavailable")

    return suggestions or ["Review test logic and ensure it matches current implementation"]


async def repair_failing_tests(repo_path: str, test_output: str) -> str:
    """Analyze test failures and provide repair suggestions."""
    logger.info("Starting failure-repair analysis for repo_path=%s", repo_path)

    if not repo_path.strip():
        logger.warning("Repair analysis aborted: repository path was empty")
        return "❌ Error: Repository path is required"
    if not test_output.strip():
        logger.warning("Repair analysis aborted: test output was empty")
        return "⚠️ No test output provided. Run execute_tests first to get failure details."

    failures = _parse_test_failures(test_output)
    if not failures:
        logger.info("Repair analysis complete: no failures detected")
        return "✅ No test failures detected - all tests passing!"

    logger.info("Repair analysis found %d failing test blocks", len(failures))

    result = ["🔧 Test Repair Analysis", "", f"Found {len(failures)} failing test(s)", ""]

    for i, failure in enumerate(failures, 1):
        result.append(f"{i}. {failure.get('test', 'Unknown test')}")
        for suggestion in _generate_test_repair(failure):
            result.append(f"   💡 {suggestion}")
        result.append("")

    result.extend(
        [
            "🔄 Recommended Actions:",
            "1. Review the specific assertions in failing tests",
            "2. Check if implementation changed without updating tests",
            "3. Verify test data and fixtures are correct",
            "4. Re-run tests after making corrections",
        ]
    )

    return "\n".join(result)
