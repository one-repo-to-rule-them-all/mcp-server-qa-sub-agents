"""Repair agent for parsing failures and suggesting fixes."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("qa-council-server.repair-agent")


def _parse_test_failures(pytest_output: str) -> list[dict]:
    """Parse pytest console output and extract per-test failure blocks.

    Handles three pytest output formats:
    - FAILURES section: ``= FAILURES =`` block with ``___ test_name ___`` delimiters
    - Short summary: lines starting with ``FAILED tests/foo.py::bar - Error``
    - Verbose format: lines ending with ``FAILED [ 25%]``
    """
    failures: list[dict] = []
    lines = pytest_output.split("\n")
    current_failure: dict = {}
    in_failure_section = False

    for line in lines:
        stripped = line.strip()

        # Detect the "= FAILURES =" section header
        if re.match(r"^=+\s*FAILURES\s*=+$", stripped):
            in_failure_section = True
            continue

        # Detect end of FAILURES section (next "===..." boundary that is not FAILURES)
        if in_failure_section and re.match(r"^=+\s*\S", stripped) and "FAILURES" not in stripped:
            in_failure_section = False
            if current_failure.get("lines"):
                failures.append(current_failure)
                current_failure = {}

        # Inside FAILURES section, capture individual test failure blocks
        if in_failure_section:
            underline_match = re.match(r"^_+\s*(.+?)\s*_+$", stripped)
            if underline_match:
                if current_failure.get("lines"):
                    failures.append(current_failure)
                current_failure = {"test": underline_match.group(1), "lines": []}
            elif current_failure.get("test"):
                current_failure.setdefault("lines", []).append(line)
            continue

        # Format 1: Short summary lines starting with FAILED
        if stripped.startswith("FAILED"):
            parts = stripped.split(None, 1)
            test_name = parts[1].split(" - ")[0] if len(parts) > 1 else stripped
            error_msg = ""
            if " - " in stripped:
                error_msg = stripped.split(" - ", 1)[1]
            failures.append({
                "test": test_name,
                "lines": [error_msg] if error_msg else [],
            })
            continue

        # Format 2: Verbose lines ending with FAILED (e.g. "test_foo FAILED [ 25%]")
        if re.search(r"\bFAILED\b\s*\[?\s*\d*%?\s*\]?\s*$", stripped):
            test_part = re.sub(r"\s+FAILED\s*\[?\s*\d*%?\s*\]?\s*$", "", stripped)
            failures.append({
                "test": test_part.strip(),
                "lines": [],
            })
            continue

    # Flush any remaining failure block from the FAILURES section
    if current_failure.get("lines"):
        failures.append(current_failure)

    # Fallback heuristics for environment/invocation errors
    if not failures:
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
    if "ValidationError" in failure_text or "pydantic" in failure_text.lower():
        suggestions.append("Check Pydantic model constructor - required fields may be missing or have wrong types")
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
