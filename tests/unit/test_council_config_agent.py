"""Unit tests for council configuration generation agent."""

from __future__ import annotations

import pytest

from qa_agents.council_config_agent import generate_council_configuration


@pytest.mark.unit
class TestGenerateCouncilConfiguration:
    """Validate council config + workflow artifacts for autonomous QA lifecycle."""

    @pytest.mark.asyncio
    async def test_rejects_empty_repo_path(self):
        result = await generate_council_configuration("")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_returns_error_for_invalid_repo_path(self):
        result = await generate_council_configuration("/definitely/not/here")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_generates_config_and_workflow(self, tmp_repo):
        result = await generate_council_configuration(str(tmp_repo))

        assert "✅" in result

        config_file = tmp_repo / ".qa-council" / "council-config.yml"
        workflow_file = tmp_repo / ".github" / "workflows" / "qa_council_autofix.yml"

        assert config_file.exists()
        assert workflow_file.exists()

        config_content = config_file.read_text(encoding="utf-8")
        workflow_content = workflow_file.read_text(encoding="utf-8")

        assert "sub_agents:" in config_content
        assert "frontend: true" in config_content
        assert "backend: true" in config_content
        assert "healing-engine" in config_content

        assert "workflow_dispatch" in workflow_content
        assert "create-pull-request@v7" in workflow_content
        assert "qa/council/autofix" in workflow_content

    @pytest.mark.asyncio
    async def test_detects_frontend_only_repo(self, tmp_path):
        repo = tmp_path / "frontend_repo"
        (repo / "frontend" / "src").mkdir(parents=True)
        (repo / "frontend" / "src" / "App.tsx").write_text("export default function App() { return null; }")

        await generate_council_configuration(str(repo))

        config_file = repo / ".qa-council" / "council-config.yml"
        content = config_file.read_text(encoding="utf-8")

        assert "frontend: true" in content
        assert "backend: false" in content
