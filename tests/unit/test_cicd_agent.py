from pathlib import Path

import pytest

from qa_agents.cicd_agent import generate_github_workflow


@pytest.mark.asyncio
async def test_generate_github_workflow_writes_file_and_skips_dispatch_without_token(tmp_path: Path):
    result = await generate_github_workflow(
        repo_path=str(tmp_path),
        test_command="pytest -q",
        trigger_workflow="true",
        workflow_repo="one-repo-to-rule-them-all/media-collection-tracker",
    )

    workflow_path = tmp_path / ".github" / "workflows" / "qa_testing.yml"
    assert workflow_path.exists()
    assert "workflow_dispatch" in workflow_path.read_text(encoding="utf-8")
    assert "⚠️ Workflow dispatch skipped: GITHUB_TOKEN is not configured" in result
