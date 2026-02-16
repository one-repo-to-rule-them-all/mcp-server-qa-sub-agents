"""Integration tests for qa_council_server.orchestrate_full_qa_cycle.

These tests verify the full agent orchestration pipeline with mocked
subprocess calls so no real git/pytest operations occur.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.integration
class TestOrchestrateFullQACycle:
    """Verify the end-to-end agent orchestration pipeline."""

    @pytest.fixture(autouse=True)
    def _patch_directories(self, tmp_path):
        """Redirect workspace/results/coverage dirs to temp for isolation."""
        self.workspace = tmp_path / "repos"
        self.workspace.mkdir()
        self.results = tmp_path / "results"
        self.results.mkdir()
        self.coverage = tmp_path / "coverage"
        self.coverage.mkdir()

    @pytest.mark.asyncio
    async def test_rejects_empty_repo_url(self):
        from qa_council_server import orchestrate_full_qa_cycle

        result = await orchestrate_full_qa_cycle(repo_url="", branch="main")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_halts_on_clone_failure(self):
        from qa_council_server import orchestrate_full_qa_cycle

        with patch(
            "qa_council_server.clone_repository",
            new_callable=AsyncMock,
            return_value="❌ Repository clone failed: not found",
        ):
            result = await orchestrate_full_qa_cycle(
                repo_url="https://github.com/owner/repo",
            )

        assert "❌" in result
        # Should halt after repository agent – no analyzer/generator output
        assert "AGENT 2" not in result

    @pytest.mark.asyncio
    async def test_full_cycle_with_all_agents_passing(self, tmp_repo):
        from qa_council_server import orchestrate_full_qa_cycle

        repo_path = str(tmp_repo)

        with patch(
            "qa_council_server.clone_repository",
            new_callable=AsyncMock,
            return_value=f"✅ Repository ready at: {repo_path}",
        ), patch(
            "qa_council_server.analyze_codebase",
            new_callable=AsyncMock,
            return_value="📊 Codebase Analysis Complete\nFiles analyzed: 5",
        ), patch(
            "qa_council_server.generate_unit_tests",
            new_callable=AsyncMock,
            return_value="✅ Unit tests generated successfully",
        ), patch(
            "qa_council_server.generate_e2e_tests",
            new_callable=AsyncMock,
            return_value="✅ E2E tests generated",
        ), patch(
            "qa_council_server.execute_tests",
            new_callable=AsyncMock,
            return_value="✅ Test Execution Complete\nPassed: 10\nFailed: 0",
        ), patch(
            "qa_council_server.generate_github_workflow",
            new_callable=AsyncMock,
            return_value="✅ GitHub Actions workflow generated",
        ):
            result = await orchestrate_full_qa_cycle(
                repo_url="https://github.com/owner/repo",
                base_url="http://localhost:3000",
            )

        assert "AGENT 1" in result
        assert "AGENT 2" in result
        assert "AGENT 3" in result
        assert "AGENT 4" in result
        assert "AGENT 6" in result
        assert "COMPLETE" in result
        assert "COMPLETE" in result

    @pytest.mark.asyncio
    async def test_triggers_repair_agent_on_test_failure(self, tmp_repo):
        from qa_council_server import orchestrate_full_qa_cycle

        repo_path = str(tmp_repo)

        with patch(
            "qa_council_server.clone_repository",
            new_callable=AsyncMock,
            return_value=f"✅ Repository ready at: {repo_path}",
        ), patch(
            "qa_council_server.analyze_codebase",
            new_callable=AsyncMock,
            return_value="📊 Analysis done",
        ), patch(
            "qa_council_server.generate_unit_tests",
            new_callable=AsyncMock,
            return_value="✅ Tests generated",
        ), patch(
            "qa_council_server.execute_tests",
            new_callable=AsyncMock,
            return_value="⚠️ Test Execution Complete\nPassed: 3\nFailed: 2\nFAILED tests/test_x.py",
        ), patch(
            "qa_council_server.repair_failing_tests",
            new_callable=AsyncMock,
            return_value="🔧 Test Repair Analysis\n2 failures analyzed",
        ), patch(
            "qa_council_server.generate_github_workflow",
            new_callable=AsyncMock,
            return_value="✅ Workflow generated",
        ):
            result = await orchestrate_full_qa_cycle(
                repo_url="https://github.com/owner/repo",
            )

        # Repair agent should be invoked (Agent 5)
        assert "AGENT 5" in result
        assert "Repair" in result

    @pytest.mark.asyncio
    async def test_self_healing_retries_on_failure(self, tmp_repo):
        """Orchestrator should retry execute→repair up to 3 times."""
        from qa_council_server import orchestrate_full_qa_cycle

        repo_path = str(tmp_repo)
        exec_call_count = 0

        async def mock_execute(**kwargs):
            nonlocal exec_call_count
            exec_call_count += 1
            if exec_call_count < 3:
                return "⚠️ Test Execution Complete\nPassed: 3\nFAILED test_x.py"
            return "✅ Test Execution Complete\nPassed: 5"

        with patch(
            "qa_council_server.clone_repository",
            new_callable=AsyncMock,
            return_value=f"✅ Repository ready at: {repo_path}",
        ), patch(
            "qa_council_server.analyze_codebase",
            new_callable=AsyncMock,
            return_value="📊 Done",
        ), patch(
            "qa_council_server.generate_unit_tests",
            new_callable=AsyncMock,
            return_value="✅ Generated",
        ), patch(
            "qa_council_server.execute_tests",
            side_effect=mock_execute,
        ), patch(
            "qa_council_server.repair_failing_tests",
            new_callable=AsyncMock,
            return_value="🔧 Repair applied",
        ), patch(
            "qa_council_server.generate_github_workflow",
            new_callable=AsyncMock,
            return_value="✅ Workflow",
        ):
            result = await orchestrate_full_qa_cycle(
                repo_url="https://github.com/owner/repo",
            )

        # Should have run executor 3 times, repair 2 times, then succeeded
        assert exec_call_count == 3
        assert "attempt 1/3" in result
        assert "attempt 2/3" in result
        assert "attempt 3/3" in result
        assert "All tests passing" in result

    @pytest.mark.asyncio
    async def test_self_healing_exhaustion(self, tmp_repo):
        """Orchestrator should report exhaustion after max retries."""
        from qa_council_server import orchestrate_full_qa_cycle

        repo_path = str(tmp_repo)

        with patch(
            "qa_council_server.clone_repository",
            new_callable=AsyncMock,
            return_value=f"✅ Repository ready at: {repo_path}",
        ), patch(
            "qa_council_server.analyze_codebase",
            new_callable=AsyncMock,
            return_value="📊 Done",
        ), patch(
            "qa_council_server.generate_unit_tests",
            new_callable=AsyncMock,
            return_value="✅ Generated",
        ), patch(
            "qa_council_server.execute_tests",
            new_callable=AsyncMock,
            return_value="⚠️ Failed: 2\nFAILED test_x.py",
        ), patch(
            "qa_council_server.repair_failing_tests",
            new_callable=AsyncMock,
            return_value="🔧 Repair attempted",
        ), patch(
            "qa_council_server.generate_github_workflow",
            new_callable=AsyncMock,
            return_value="✅ Workflow",
        ):
            result = await orchestrate_full_qa_cycle(
                repo_url="https://github.com/owner/repo",
            )

        assert "exhausted" in result.lower()
        assert "3 attempts" in result

    @pytest.mark.asyncio
    async def test_discovers_frontend_entrypoint(self, tmp_repo):
        """Orchestrator should auto-detect frontend/src/App.tsx."""
        from qa_council_server import _discover_frontend_entrypoint

        found = _discover_frontend_entrypoint(str(tmp_repo))
        assert found is not None
        assert "App.tsx" in found

    @pytest.mark.asyncio
    async def test_no_frontend_when_missing(self, tmp_path):
        """Orchestrator should return None when no frontend entrypoint exists."""
        from qa_council_server import _discover_frontend_entrypoint

        repo = tmp_path / "empty_repo"
        repo.mkdir()
        found = _discover_frontend_entrypoint(str(repo))
        assert found is None
