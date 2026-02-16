"""Unit tests for qa_agents.repair_agent – failure parsing and repair suggestions."""

from __future__ import annotations

import pytest

from qa_agents.repair_agent import (
    _generate_test_repair,
    _parse_test_failures,
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
        # Parser captures line.split()[0] which is "FAILED"
        assert failures[0]["test"] == "FAILED"

    def test_parses_failures_separated_by_terminator(self):
        """Multiple failures need a terminator line (===) between them."""
        output = (
            "FAILED tests/test_a.py::test_one\n"
            "    TypeError: bad arg\n"
            "=== separator ===\n"
            "FAILED tests/test_b.py::test_two\n"
            "    ImportError: no module\n"
            "=== 2 failed ===\n"
        )
        failures = _parse_test_failures(output)
        assert len(failures) == 2

    def test_returns_empty_for_all_passing(self):
        output = "=== 5 passed in 1.0s ===\n"
        failures = _parse_test_failures(output)
        assert failures == []

    def test_returns_empty_for_empty_output(self):
        failures = _parse_test_failures("")
        assert failures == []


@pytest.mark.unit
class TestGenerateTestRepair:
    """Verify heuristic repair suggestion generation."""

    def test_suggests_assertion_fix(self):
        failure = {"lines": ["AssertionError: assert 1 == 2"]}
        suggestions = _generate_test_repair(failure)
        assert any("assertion" in s.lower() for s in suggestions)

    def test_suggests_attribute_fix(self):
        failure = {"lines": ["AttributeError: 'NoneType' object has no attribute 'x'"]}
        suggestions = _generate_test_repair(failure)
        assert any("attribute" in s.lower() for s in suggestions)

    def test_suggests_type_fix(self):
        failure = {"lines": ["TypeError: expected str, got int"]}
        suggestions = _generate_test_repair(failure)
        assert any("type" in s.lower() or "argument" in s.lower() for s in suggestions)

    def test_suggests_import_fix(self):
        failure = {"lines": ["ModuleNotFoundError: No module named 'foo'"]}
        suggestions = _generate_test_repair(failure)
        assert any("import" in s.lower() or "module" in s.lower() for s in suggestions)

    def test_suggests_fixture_fix(self):
        failure = {"lines": ["fixture 'db_session' not found"]}
        suggestions = _generate_test_repair(failure)
        assert any("fixture" in s.lower() for s in suggestions)

    def test_provides_generic_suggestion_for_unknown_error(self):
        failure = {"lines": ["SomeRandomError: something weird"]}
        suggestions = _generate_test_repair(failure)
        assert len(suggestions) >= 1


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
        assert "1 failing test" in result
        assert "💡" in result
