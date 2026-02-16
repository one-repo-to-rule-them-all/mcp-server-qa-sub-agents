"""Unit tests for qa_agents.analyzer_agent – codebase analysis."""

from __future__ import annotations

import pytest

from qa_agents.analyzer_agent import analyze_codebase


@pytest.mark.unit
class TestAnalyzCodebase:
    """Verify codebase scanning and result formatting."""

    @pytest.mark.asyncio
    async def test_rejects_empty_path(self):
        result = await analyze_codebase("", "*.py")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_reports_no_files_for_wrong_pattern(self, tmp_repo):
        result = await analyze_codebase(str(tmp_repo), "*.rs")
        assert "⚠️" in result

    @pytest.mark.asyncio
    async def test_analyzes_python_files(self, tmp_repo):
        result = await analyze_codebase(str(tmp_repo), "*.py")

        assert "📊" in result
        assert "Files analyzed" in result
        assert "Functions found" in result
        assert "Classes found" in result

    @pytest.mark.asyncio
    async def test_returns_error_for_invalid_path(self):
        result = await analyze_codebase("/nonexistent/path/xyz", "*.py")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_lists_top_files(self, tmp_repo):
        result = await analyze_codebase(str(tmp_repo), "*.py")

        # Should list files under "Top files for testing"
        assert "Top files" in result
