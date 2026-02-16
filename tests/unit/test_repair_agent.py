"""Unit tests for qa_agents.repair_agent – failure parsing, repair plans, and self-healing."""

from __future__ import annotations

import pytest

from qa_agents.repair_agent import (
    RepairAction,
    RepairPlan,
    _generate_test_repair,
    _parse_test_failures,
    apply_repair_plan,
    build_repair_plan,
    repair_failing_tests,
)


@pytest.mark.unit
class TestParseTestFailures:
    """Verify pytest output parsing into structured failure blocks."""

    def test_parses_single_failure(self):
        output = (
            "FAILED tests/test_a.py::test_foo - AssertionError\n"
            "    assert 1 == 2\n"
            "=== 1 failed ===\n"
        )
        failures = _parse_test_failures(output)
        assert len(failures) == 1
        assert "test_a.py::test_foo" in failures[0]["test"]

    def test_parses_consecutive_failures(self):
        """Consecutive FAILED lines should flush the prior failure."""
        output = (
            "FAILED tests/test_a.py::test_one\n"
            "    TypeError: bad arg\n"
            "FAILED tests/test_b.py::test_two\n"
            "    ImportError: no module\n"
            "=== 2 failed ===\n"
        )
        failures = _parse_test_failures(output)
        assert len(failures) == 2

    def test_flushes_trailing_failure(self):
        """Failure at end of output without terminator should still be captured."""
        output = (
            "FAILED tests/test_a.py::test_x\n"
            "    RuntimeError: boom\n"
        )
        failures = _parse_test_failures(output)
        assert len(failures) == 1

    def test_returns_empty_for_all_passing(self):
        failures = _parse_test_failures("=== 5 passed in 1.0s ===\n")
        assert failures == []

    def test_returns_empty_for_empty_output(self):
        assert _parse_test_failures("") == []


@pytest.mark.unit
class TestGenerateTestRepair:
    """Verify heuristic repair suggestion generation."""

    def test_suggests_assertion_fix(self):
        failure = {"lines": ["AssertionError: assert 1 == 2"]}
        assert any("assertion" in s.lower() for s in _generate_test_repair(failure))

    def test_suggests_attribute_fix(self):
        failure = {"lines": ["AttributeError: 'NoneType' has no attr 'x'"]}
        assert any("attribute" in s.lower() for s in _generate_test_repair(failure))

    def test_suggests_type_fix(self):
        failure = {"lines": ["TypeError: expected str"]}
        assert any("type" in s.lower() or "argument" in s.lower() for s in _generate_test_repair(failure))

    def test_suggests_import_fix(self):
        failure = {"lines": ["ModuleNotFoundError: No module named 'foo'"]}
        assert any("import" in s.lower() or "module" in s.lower() for s in _generate_test_repair(failure))

    def test_suggests_fixture_fix(self):
        failure = {"lines": ["fixture 'db_session' not found"]}
        assert any("fixture" in s.lower() for s in _generate_test_repair(failure))

    def test_generic_suggestion_for_unknown_error(self):
        failure = {"lines": ["SomeRandomError: weird"]}
        assert len(_generate_test_repair(failure)) >= 1


@pytest.mark.unit
class TestBuildRepairPlan:
    """Verify structured repair plan construction."""

    def test_empty_plan_for_no_failures(self):
        plan = build_repair_plan("/repo", "=== 5 passed ===")
        assert plan.actions == []
        assert "No failures" in plan.summary

    def test_plan_with_import_fix(self, tmp_path):
        test_file = tmp_path / "tests" / "test_bad.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("import nonexistent_module\n\ndef test_x():\n    pass\n")

        output = (
            f"FAILED tests/test_bad.py::test_x\n"
            "    ModuleNotFoundError: No module named 'nonexistent_module'\n"
            "=== 1 failed ===\n"
        )
        plan = build_repair_plan(str(tmp_path), output)

        assert len(plan.actions) == 1
        assert "nonexistent_module" in plan.actions[0].reason
        assert "FIXME" in plan.actions[0].new_content

    def test_plan_with_assertion_fix(self, tmp_path):
        test_file = tmp_path / "tests" / "test_assert.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("import pytest\n\ndef test_value():\n    assert 1 == 2\n")

        output = (
            "FAILED tests/test_assert.py::test_value\n"
            "    AssertionError: assert 1 == 2\n"
            "=== 1 failed ===\n"
        )
        plan = build_repair_plan(str(tmp_path), output)

        assert len(plan.actions) == 1
        assert "skip" in plan.actions[0].reason.lower()

    def test_plan_collects_suggestions(self, tmp_path):
        output = (
            "FAILED tests/test_x.py::test_z\n"
            "    TypeError: bad args\n"
            "=== 1 failed ===\n"
        )
        plan = build_repair_plan(str(tmp_path), output)
        assert len(plan.suggestions) >= 1


@pytest.mark.unit
class TestApplyRepairPlan:
    """Verify repair plan application writes files to disk."""

    def test_applies_action_to_file(self, tmp_path):
        target = tmp_path / "test_file.py"
        target.write_text("original content")

        plan = RepairPlan(
            actions=[
                RepairAction(
                    file_path=str(target),
                    old_content="original content",
                    new_content="fixed content",
                    reason="Test fix",
                )
            ]
        )

        applied = apply_repair_plan(plan)

        assert len(applied) == 1
        assert target.read_text() == "fixed content"

    def test_handles_write_failure(self, tmp_path):
        plan = RepairPlan(
            actions=[
                RepairAction(
                    file_path=str(tmp_path / "nonexistent_dir" / "file.py"),
                    old_content="old",
                    new_content="new",
                    reason="Should fail",
                )
            ]
        )

        applied = apply_repair_plan(plan)
        assert len(applied) == 0

    def test_empty_plan_applies_nothing(self):
        applied = apply_repair_plan(RepairPlan())
        assert applied == []


@pytest.mark.unit
class TestRepairFailingTests:
    """Verify the async entry point of the repair agent."""

    @pytest.mark.asyncio
    async def test_rejects_empty_repo_path(self):
        result = await repair_failing_tests("", "some output")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_rejects_empty_test_output(self, tmp_repo):
        result = await repair_failing_tests(str(tmp_repo), "")
        assert "⚠️" in result

    @pytest.mark.asyncio
    async def test_returns_passing_when_no_failures(self, tmp_repo):
        result = await repair_failing_tests(str(tmp_repo), "=== 5 passed ===")
        assert "✅" in result

    @pytest.mark.asyncio
    async def test_returns_analysis_with_suggestions(self, tmp_repo):
        output = (
            "FAILED tests/test_a.py::test_foo\n"
            "    AssertionError: assert False\n"
            "=== 1 failed ===\n"
        )
        result = await repair_failing_tests(str(tmp_repo), output)

        assert "🔧" in result
        assert "1 failure" in result
        assert "💡" in result
