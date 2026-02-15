"""Repair Agent: diagnose and fix test failures.

Responsible for parsing pytest output to identify failures,
pattern-matching common error types, and generating actionable
repair suggestions.
"""
from utils.config import get_logger

logger = get_logger("repair")


def parse_test_failures(pytest_output: str) -> list:
    """Parse pytest output to extract failure information.

    Args:
        pytest_output: Raw stdout from a pytest run

    Returns:
        List of failure dicts, each with 'test' name and 'lines' of error detail.
    """
    failures = []
    lines = pytest_output.split('\n')

    current_failure = {}
    in_failure = False

    for line in lines:
        if line.startswith("FAILED"):
            in_failure = True
            current_failure = {"test": line.split()[0], "lines": []}
        elif in_failure:
            if line.startswith("===") or line.startswith("PASSED") or line.startswith("FAILED"):
                if current_failure.get("lines"):
                    failures.append(current_failure)
                current_failure = {}
                in_failure = False
            else:
                current_failure.get("lines", []).append(line)

    # Capture last failure if output ended without separator
    if in_failure and current_failure.get("lines"):
        failures.append(current_failure)

    return failures


def generate_test_repair(failure_info: dict) -> list:
    """Generate repair suggestions for a single test failure.

    Uses pattern matching on error text to provide targeted advice.

    Args:
        failure_info: Dict with 'test' and 'lines' keys

    Returns:
        List of suggestion strings.
    """
    suggestions = []
    failure_text = '\n'.join(failure_info.get("lines", []))

    if "AssertionError" in failure_text or "AssertionError" in failure_text:
        suggestions.append(
            "Check assertion conditions - expected vs actual values may not match"
        )
    if "AttributeError" in failure_text:
        suggestions.append(
            "Verify object attributes and method names are correct"
        )
    if "TypeError" in failure_text:
        suggestions.append(
            "Check function argument types and counts"
        )
    if "ImportError" in failure_text or "ModuleNotFoundError" in failure_text:
        suggestions.append(
            "Ensure all required modules are installed and import paths are correct"
        )
    if "fixture" in failure_text.lower():
        suggestions.append(
            "Verify pytest fixtures are properly defined and scoped"
        )
    if "FileNotFoundError" in failure_text:
        suggestions.append(
            "Check file paths and ensure test data files exist"
        )
    if "ConnectionError" in failure_text or "TimeoutError" in failure_text:
        suggestions.append(
            "Mock external service calls to avoid network dependencies in tests"
        )
    if "mock" in failure_text.lower() or "patch" in failure_text.lower():
        suggestions.append(
            "Verify mock targets match the actual import path in the module under test"
        )

    if not suggestions:
        suggestions.append(
            "Review test logic and ensure it matches current implementation"
        )

    return suggestions


async def run_repair_analysis(repo_path: str = "", test_output: str = "") -> str:
    """Analyze test failures and provide repair suggestions.

    Args:
        repo_path: Path to the repository
        test_output: Raw pytest output containing failure details

    Returns:
        Formatted analysis with per-failure suggestions and action items.
    """
    if not repo_path.strip():
        return "Error: Repository path is required"

    logger.info(f"Analyzing test failures for: {repo_path}")

    if not test_output.strip():
        return "No test output provided. Run execute_tests first to get failure details."

    try:
        failures = parse_test_failures(test_output)

        if not failures:
            return "No test failures detected - all tests passing!"

        result = "Test Repair Analysis\n\n"
        result += f"Found {len(failures)} failing test(s)\n\n"

        for i, failure in enumerate(failures, 1):
            result += f"{i}. {failure.get('test', 'Unknown test')}\n"
            suggestions = generate_test_repair(failure)
            for suggestion in suggestions:
                result += f"   - {suggestion}\n"
            result += "\n"

        result += "\nRecommended Actions:\n"
        result += "1. Review the specific assertions in failing tests\n"
        result += "2. Check if implementation changed without updating tests\n"
        result += "3. Verify test data and fixtures are correct\n"
        result += "4. Re-run tests after making corrections\n"

        return result
    except Exception as e:
        logger.error(f"Repair analysis error: {e}")
        return f"Error analyzing failures: {str(e)}"
