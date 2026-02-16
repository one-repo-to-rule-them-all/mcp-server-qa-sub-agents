"""Unit tests for qa_agents.cicd_agent – GitHub workflow generation and dispatch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from qa_agents.cicd_agent import generate_github_workflow


@pytest.mark.unit
class TestGenerateGithubWorkflow:
    """Verify workflow YAML generation, file writing, and dispatch triggering."""

    @pytest.mark.asyncio
    async def test_rejects_empty_repo_path(self):
        result = await generate_github_workflow("", trigger_workflow="false")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_returns_error_for_invalid_path(self):
        result = await generate_github_workflow("/nonexistent/path", trigger_workflow="false")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_generates_workflow_file(self, tmp_repo):
        result = await generate_github_workflow(
            str(tmp_repo), test_command="pytest -v", trigger_workflow="false",
        )

        assert "✅" in result

        workflow_file = tmp_repo / ".github" / "workflows" / "qa_testing.yml"
        assert workflow_file.exists()

        content = workflow_file.read_text()
        assert "pytest -v" in content
        assert "actions/checkout@v4" in content
        assert "actions/setup-python@v5" in content
        assert "workflow_dispatch" in content
        assert "playwright install" in content

    @pytest.mark.asyncio
    async def test_workflow_has_correct_triggers(self, tmp_repo):
        await generate_github_workflow(str(tmp_repo), trigger_workflow="false")

        workflow_file = tmp_repo / ".github" / "workflows" / "qa_testing.yml"
        content = workflow_file.read_text()

        assert "push:" in content
        assert "pull_request:" in content
        assert "workflow_dispatch:" in content

    @pytest.mark.asyncio
    async def test_skips_dispatch_when_disabled(self, tmp_repo):
        result = await generate_github_workflow(
            str(tmp_repo), trigger_workflow="false",
        )

        assert "skipped" in result.lower()

    @pytest.mark.asyncio
    async def test_triggers_dispatch_when_enabled(self, tmp_repo, mock_github_token):
        mock_response = MagicMock()
        mock_response.status_code = 204

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("qa_agents.cicd_agent.httpx.AsyncClient", return_value=mock_client), \
             patch("qa_agents.cicd_agent.get_repo_identifier_from_local_repo", return_value="owner/repo"):
            result = await generate_github_workflow(
                str(tmp_repo),
                trigger_workflow="true",
                workflow_repo="owner/repo",
            )

        assert "🚀" in result or "Triggered" in result

    @pytest.mark.asyncio
    async def test_handles_dispatch_401_unauthorized(self, tmp_repo, mock_github_token):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Bad credentials"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("qa_agents.cicd_agent.httpx.AsyncClient", return_value=mock_client), \
             patch("qa_agents.cicd_agent.get_repo_identifier_from_local_repo", return_value="owner/repo"):
            result = await generate_github_workflow(
                str(tmp_repo),
                trigger_workflow="true",
                workflow_repo="owner/repo",
            )

        assert "401" in result or "Unauthorized" in result
