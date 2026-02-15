"""Repair agent for parsing failures and suggesting fixes."""

from __future__ import annotations


def _parse_test_failures(pytest_output: str) -> list[dict]:
    failures = []
    lines = pytest_output.split("\n")
    current_failure = {}
    in_failure = False

    for line in lines:
        if line.startswith("FAILED"):
            in_failure = True
            current_failure = {"test": line.split()[0], "lines": []}
        elif in_failure:
            if line.startswith(("===", "PASSED", "FAILED")):
                if current_failure.get("lines"):
                    failures.append(current_failure)
                current_failure = {}
                in_failure = False
            else:
                current_failure.setdefault("lines", []).append(line)

    return failures


def _generate_test_repair(failure_info: dict) -> list[str]:
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

    return suggestions or ["Review test logic and ensure it matches current implementation"]


async def repair_failing_tests(repo_path: str, test_output: str) -> str:
    """Analyze test failures and provide repair suggestions."""
    if not repo_path.strip():
        return "❌ Error: Repository path is required"
    if not test_output.strip():
        return "⚠️ No test output provided. Run execute_tests first to get failure details."

    failures = _parse_test_failures(test_output)
    if not failures:
        return "✅ No test failures detected - all tests passing!"

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
