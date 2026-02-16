"""Unit tests for qa_agents.github_pr_agent – branch creation and PR submission."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from qa_agents.github_pr_agent import _extract_github_info, create_test_fix_pr


@pytest.mark.unit
class TestExtractGithubInfo:
    """Verify owner/repo extraction from GitHub URLs."""

    def test_standard_https_url(self):
        owner, repo = _extract_github_info("https://github.com/myorg/myrepo")
        assert owner == "myorg"
        assert repo == "myrepo"

    def test_url_with_git_suffix(self):
        owner, repo = _extract_github_info("https://github.com/myorg/myrepo.git")
        assert repo == "myrepo"

    def test_trailing_slash(self):
        owner, repo = _extract_github_info("https://github.com/myorg/myrepo/")
        assert owner == "myorg"
        assert repo == "myrepo"

    def test_non_github_url(self):
        owner, repo = _extract_github_info("https://gitlab.com/myorg/myrepo")
        assert owner is None
        assert repo is None

    def test_short_url(self):
        owner, repo = _extract_github_info("github.com")
        assert owner is None


@pytest.mark.unit
class TestCreateTestFixPr:
    """Verify the end-to-end PR creation flow."""

    @pytest.mark.asyncio
    async def test_rejects_empty_url(self, tmp_path):
        result = await create_test_fix_pr("", "output", "", tmp_path)
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_rejects_invalid_github_url(self, tmp_path):
        result = await create_test_fix_pr("https://gitlab.com/org/repo", "output", "", tmp_path)
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_rejects_missing_token(self, tmp_path, clean_env):
        result = await create_test_fix_pr(
            "https://github.com/org/repo", "output", "", tmp_path,
        )
        assert "❌" in result
        assert "GITHUB_TOKEN" in result

    @pytest.mark.asyncio
    async def test_creates_pr_successfully(self, tmp_path, mock_github_token):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        fixes = json.dumps([{"file": "tests/test_fix.py", "content": "# fixed", "description": "Fix test"}])

        mock_branch = AsyncMock(return_value=(True, "qa-council/test-fixes-20240101"))
        mock_pr = AsyncMock(return_value=(True, "https://github.com/org/repo/pull/42"))

        with patch("qa_agents.github_pr_agent._create_test_fix_branch", mock_branch), \
             patch("qa_agents.github_pr_agent._create_github_pr", mock_pr):
            result = await create_test_fix_pr(
                "https://github.com/org/repo",
                "2 failed",
                fixes,
                tmp_path,
            )

        assert "✅" in result
        assert "pull/42" in result

    @pytest.mark.asyncio
    async def test_handles_branch_creation_failure(self, tmp_path, mock_github_token):
        fixes = json.dumps([{"file": "test.py", "content": "# x", "description": "fix"}])

        mock_branch = AsyncMock(return_value=(False, "git checkout failed"))

        with patch("qa_agents.github_pr_agent._create_test_fix_branch", mock_branch):
            result = await create_test_fix_pr(
                "https://github.com/org/repo",
                "1 failed",
                fixes,
                tmp_path,
            )

        assert "❌" in result

    @pytest.mark.asyncio
    async def test_handles_invalid_fixes_json(self, tmp_path, mock_github_token):
        mock_pr = AsyncMock(return_value=(True, "https://github.com/org/repo/pull/1"))

        with patch("qa_agents.github_pr_agent._create_github_pr", mock_pr):
            result = await create_test_fix_pr(
                "https://github.com/org/repo",
                "output",
                "not valid json {{",
                tmp_path,
            )

        # Should proceed without file changes (fix_list becomes [])
        assert "✅" in result or "❌" not in result
