"""Unit tests for qa_agents.repository_agent – clone/update operations."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qa_agents.repository_agent import clone_repository


@pytest.mark.unit
class TestCloneRepository:
    """Verify clone, pull, token injection, and error handling."""

    @pytest.mark.asyncio
    async def test_rejects_empty_url(self, tmp_path):
        result = await clone_repository("", "main", tmp_path)
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_clones_new_repo(self, tmp_path):
        mock_run = MagicMock()
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("qa_agents.repository_agent.subprocess.run", mock_run), \
             patch("qa_agents.repository_agent.get_github_token", return_value=""):
            result = await clone_repository(
                "https://github.com/owner/repo", "main", tmp_path,
            )

        assert "✅" in result
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "clone" in call_args

    @pytest.mark.asyncio
    async def test_pulls_existing_repo(self, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        mock_run = MagicMock()
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("qa_agents.repository_agent.subprocess.run", mock_run):
            result = await clone_repository(
                "https://github.com/owner/repo", "main", tmp_path,
            )

        assert "✅" in result
        call_args = mock_run.call_args[0][0]
        assert "pull" in call_args

    @pytest.mark.asyncio
    async def test_injects_github_token_on_clone(self, tmp_path):
        mock_run = MagicMock()
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("qa_agents.repository_agent.subprocess.run", mock_run), \
             patch("qa_agents.repository_agent.get_github_token", return_value="ghp_token123"):
            await clone_repository(
                "https://github.com/owner/repo", "main", tmp_path,
            )

        clone_cmd = mock_run.call_args[0][0]
        # git clone -b <branch> <url> <path> → URL is at index 4
        clone_url = clone_cmd[4]
        assert "ghp_token123@" in clone_url

    @pytest.mark.asyncio
    async def test_returns_error_on_clone_failure(self, tmp_path):
        mock_run = MagicMock()
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: repo not found")

        with patch("qa_agents.repository_agent.subprocess.run", mock_run), \
             patch("qa_agents.repository_agent.get_github_token", return_value=""):
            result = await clone_repository(
                "https://github.com/owner/repo", "main", tmp_path,
            )

        assert "❌" in result

    @pytest.mark.asyncio
    async def test_handles_timeout(self, tmp_path):
        import subprocess

        with patch("qa_agents.repository_agent.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 120)), \
             patch("qa_agents.repository_agent.get_github_token", return_value=""):
            result = await clone_repository(
                "https://github.com/owner/repo", "main", tmp_path,
            )

        assert "❌" in result
        assert "timed out" in result.lower()
