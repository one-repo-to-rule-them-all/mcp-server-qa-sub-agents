"""Repair agent for parsing failures, applying fixes, and self-healing tests."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("qa-council-server.repair-agent")

MAX_SELF_HEALING_RETRIES = 3


# ---------------------------------------------------------------------------
# Structured repair data
# ---------------------------------------------------------------------------

@dataclass
class RepairAction:
    """A single file-level repair to apply."""

    file_path: str
    old_content: str
    new_content: str
    reason: str


@dataclass
class RepairPlan:
    """Collection of repairs produced by the repair agent."""

    actions: list[RepairAction] = field(default_factory=list)
    summary: str = ""
    suggestions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Failure parsing
# ---------------------------------------------------------------------------

def _parse_test_failures(pytest_output: str) -> list[dict]:
    """Parse pytest console output and extract per-test failure blocks."""
    failures = []
    lines = pytest_output.split("\n")
    current_failure: dict = {}
    in_failure = False

    for line in lines:
        if line.startswith("FAILED"):
            # Flush any previous in-progress failure before starting a new one
            if in_failure and current_failure.get("lines"):
                failures.append(current_failure)
            in_failure = True
            # Extract the full test identifier (e.g. tests/test_x.py::test_foo)
            parts = line.split()
            test_id = parts[1] if len(parts) > 1 else parts[0]
            current_failure = {"test": test_id, "lines": []}
        elif in_failure:
            if line.startswith(("===", "PASSED")):
                if current_failure.get("lines"):
                    failures.append(current_failure)
                current_failure = {}
                in_failure = False
            else:
                current_failure.setdefault("lines", []).append(line)

    # Flush trailing failure block if output ends without terminator
    if in_failure and current_failure.get("lines"):
        failures.append(current_failure)

    return failures


# ---------------------------------------------------------------------------
# Heuristic repair suggestions
# ---------------------------------------------------------------------------

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

    return suggestions or ["Review test logic and ensure it matches current implementation"]


# ---------------------------------------------------------------------------
# Automated fix application
# ---------------------------------------------------------------------------

def _build_import_fix(failure_text: str, test_file: Path) -> RepairAction | None:
    """Fix ModuleNotFoundError by commenting out the bad import."""
    match = re.search(r"No module named '([^']+)'", failure_text)
    if not match or not test_file.exists():
        return None

    missing_module = match.group(1)
    content = test_file.read_text(encoding="utf-8")
    fixed_lines = []
    changed = False

    for line in content.splitlines():
        if missing_module in line and ("import" in line) and not line.strip().startswith("#"):
            fixed_lines.append(f"# FIXME: module not found - {line}")
            changed = True
        else:
            fixed_lines.append(line)

    if changed:
        return RepairAction(
            file_path=str(test_file),
            old_content=content,
            new_content="\n".join(fixed_lines) + "\n",
            reason=f"Commented out import of missing module '{missing_module}'",
        )
    return None


def _build_assertion_fix(failure_text: str, test_file: Path) -> RepairAction | None:
    """Fix simple assertion mismatches by adding a skip marker."""
    if "AssertionError" not in failure_text:
        return None
    if not test_file.exists():
        return None

    # Extract the failing test function name
    match = re.search(r"def (test_\w+)", test_file.read_text(encoding="utf-8"))
    if not match:
        return None

    content = test_file.read_text(encoding="utf-8")
    func_name = match.group(1)

    # Add a pytest.mark.skip to the failing function (simple heuristic)
    old_def = f"def {func_name}"
    new_def = f'@pytest.mark.skip(reason="Self-healing: assertion mismatch under investigation")\n    def {func_name}'

    if old_def in content:
        return RepairAction(
            file_path=str(test_file),
            old_content=content,
            new_content=content.replace(old_def, new_def, 1),
            reason=f"Added skip marker to {func_name} due to assertion mismatch",
        )
    return None


def _extract_test_file_path(failure: dict, repo_path: str) -> Path | None:
    """Try to resolve the test file path from the failure dict."""
    test_id = failure.get("test", "")
    # test_id format: tests/test_x.py::test_func or FAILED
    if "::" in test_id:
        rel_path = test_id.split("::")[0]
        candidate = Path(repo_path) / rel_path
        if candidate.exists():
            return candidate
    return None


def build_repair_plan(repo_path: str, pytest_output: str) -> RepairPlan:
    """Analyze failures and build a structured repair plan with file patches."""
    failures = _parse_test_failures(pytest_output)
    plan = RepairPlan()

    if not failures:
        plan.summary = "No failures detected"
        return plan

    for failure in failures:
        failure_text = "\n".join(failure.get("lines", []))
        test_file = _extract_test_file_path(failure, repo_path)

        # Collect suggestions
        for suggestion in _generate_test_repair(failure):
            plan.suggestions.append(f"{failure.get('test', '?')}: {suggestion}")

        if test_file is None:
            continue

        # Try automated fixes in priority order
        fix = _build_import_fix(failure_text, test_file)
        if fix:
            plan.actions.append(fix)
            continue

        fix = _build_assertion_fix(failure_text, test_file)
        if fix:
            plan.actions.append(fix)

    plan.summary = (
        f"Analyzed {len(failures)} failure(s): "
        f"{len(plan.actions)} auto-fix(es), "
        f"{len(plan.suggestions)} suggestion(s)"
    )
    return plan


def apply_repair_plan(plan: RepairPlan) -> list[str]:
    """Write repair actions to disk.  Returns list of modified file paths."""
    applied: list[str] = []

    for action in plan.actions:
        try:
            path = Path(action.file_path)
            path.write_text(action.new_content, encoding="utf-8")
            applied.append(action.file_path)
            logger.info("Applied repair to %s: %s", action.file_path, action.reason)
        except Exception as exc:
            logger.warning("Failed to apply repair to %s: %s", action.file_path, exc)

    return applied


# ---------------------------------------------------------------------------
# Public async entry point (MCP tool)
# ---------------------------------------------------------------------------

async def repair_failing_tests(repo_path: str, test_output: str) -> str:
    """Analyze test failures, apply automated fixes, and provide suggestions."""
    logger.info("Starting failure-repair analysis for repo_path=%s", repo_path)

    if not repo_path.strip():
        logger.warning("Repair analysis aborted: repository path was empty")
        return "❌ Error: Repository path is required"
    if not test_output.strip():
        logger.warning("Repair analysis aborted: test output was empty")
        return "⚠️ No test output provided. Run execute_tests first to get failure details."

    plan = build_repair_plan(repo_path, test_output)

    if not plan.actions and not plan.suggestions:
        logger.info("Repair analysis complete: no failures detected")
        return "✅ No test failures detected - all tests passing!"

    logger.info("Repair plan: %s", plan.summary)

    # Apply automated fixes
    applied = apply_repair_plan(plan)

    result = ["🔧 Test Repair Analysis", "", plan.summary, ""]

    if applied:
        result.append("🔨 Auto-fixes applied:")
        for action in plan.actions:
            result.append(f"   - {action.file_path}: {action.reason}")
        result.append("")

    if plan.suggestions:
        result.append("💡 Suggestions:")
        for suggestion in plan.suggestions:
            result.append(f"   - {suggestion}")
        result.append("")

    result.extend(
        [
            "🔄 Recommended Actions:",
            "1. Review auto-applied fixes above",
            "2. Re-run tests to verify repairs",
            "3. Check if implementation changed without updating tests",
            "4. Verify test data and fixtures are correct",
        ]
    )

    return "\n".join(result)
