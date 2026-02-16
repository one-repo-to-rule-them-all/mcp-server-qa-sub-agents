"""Unit tests for qa_agents.executor_agent – pytest execution and result parsing."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qa_agents.executor_agent import execute_tests


@pytest.mark.unit
class TestExecuteTests:
    """Verify test execution, summary parsing, and error handling."""

    @pytest.mark.asyncio
    async def test_rejects_empty_repo_path(self):
        result = await execute_tests("", Path("/tmp/results"), Path("/tmp/coverage"))
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_returns_error_for_invalid_path(self):
        result = await execute_tests("/nonexistent/repo", Path("/tmp/results"), Path("/tmp/coverage"))
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_parses_passing_test_summary(self, tmp_repo, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "tests/test_main.py::test_health PASSED\n"
            "================ 3 passed, 0 failed in 1.23s ================\n"
            "TOTAL   100    10    90%\n"
        )
        mock_result.stderr = ""

        with patch("qa_agents.executor_agent.subprocess.run", return_value=mock_result):
            result = await execute_tests(
                str(tmp_repo),
                tmp_path / "results",
                tmp_path / "coverage",
            )

        assert "✅" in result
        assert "Coverage: 90%" in result
        assert "Report:" in result

    @pytest.mark.asyncio
    async def test_parses_failing_test_summary(self, tmp_repo, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = (
            "tests/test_main.py::test_x FAILED\n"
            "================ 1 passed, 2 failed in 0.5s ================\n"
        )
        mock_result.stderr = ""

        with patch("qa_agents.executor_agent.subprocess.run", return_value=mock_result):
            result = await execute_tests(
                str(tmp_repo),
                tmp_path / "results",
                tmp_path / "coverage",
            )

        assert "⚠️" in result
        assert "Failed:" in result

    @pytest.mark.asyncio
    async def test_handles_no_tests_collected(self, tmp_repo, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 5
        mock_result.stdout = "collected 0 items\nno tests ran in 0.01s\n"
        mock_result.stderr = ""

        with patch("qa_agents.executor_agent.subprocess.run", return_value=mock_result):
            result = await execute_tests(
                str(tmp_repo),
                tmp_path / "results",
                tmp_path / "coverage",
            )

        assert "No tests collected: True" in result

    @pytest.mark.asyncio
    async def test_handles_timeout(self, tmp_repo, tmp_path):
        with patch(
            "qa_agents.executor_agent.subprocess.run",
            side_effect=subprocess.TimeoutExpired("pytest", 300),
        ):
            result = await execute_tests(
                str(tmp_repo),
                tmp_path / "results",
                tmp_path / "coverage",
            )

        assert "❌" in result
        assert "timed out" in result.lower()
