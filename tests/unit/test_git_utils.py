"""Unit tests for qa_agents.utils.git_utils – git URL parsing and repo helpers."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from qa_agents.utils.git_utils import (
    build_git_clone_url,
    get_repo_identifier_from_local_repo,
    parse_github_repo_identifier,
    sanitize_repo_name,
)


@pytest.mark.unit
class TestSanitizeRepoName:
    """Verify URL → safe directory name conversion."""

    def test_basic_https_url(self):
        assert sanitize_repo_name("https://github.com/owner/my-repo") == "my-repo"

    def test_strips_dot_git_suffix(self):
        assert sanitize_repo_name("https://github.com/owner/repo.git") == "repo"

    def test_strips_trailing_slash(self):
        assert sanitize_repo_name("https://github.com/owner/repo/") == "repo"

    def test_sanitizes_special_characters(self):
        result = sanitize_repo_name("https://github.com/owner/repo@special!")
        assert "@" not in result
        assert "!" not in result


@pytest.mark.unit
class TestBuildGitCloneUrl:
    """Verify token injection into HTTPS clone URLs."""

    def test_injects_token_into_https(self):
        url = build_git_clone_url("https://github.com/owner/repo.git", "my_token")
        assert url == "https://my_token@github.com/owner/repo.git"

    def test_no_token_returns_original(self):
        url = build_git_clone_url("https://github.com/owner/repo.git", "")
        assert url == "https://github.com/owner/repo.git"

    def test_ssh_url_unchanged_with_token(self):
        original = "git@github.com:owner/repo.git"
        url = build_git_clone_url(original, "my_token")
        assert url == original


@pytest.mark.unit
class TestParseGithubRepoIdentifier:
    """Verify extraction of owner/repo from various URL formats."""

    def test_https_url(self):
        assert parse_github_repo_identifier("https://github.com/owner/repo") == "owner/repo"

    def test_https_url_with_git_suffix(self):
        assert parse_github_repo_identifier("https://github.com/org/project.git") == "org/project"

    def test_ssh_url(self):
        assert parse_github_repo_identifier("git@github.com:owner/repo.git") == "owner/repo"

    def test_trailing_slash(self):
        assert parse_github_repo_identifier("https://github.com/owner/repo/") == "owner/repo"

    def test_invalid_url_returns_empty(self):
        assert parse_github_repo_identifier("not-a-url") == ""


@pytest.mark.unit
class TestGetRepoIdentifierFromLocalRepo:
    """Verify reading origin remote URL from local git repos."""

    def test_returns_identifier_from_git_config(self, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/owner/repo.git\n"

        with patch("qa_agents.utils.git_utils.subprocess.run", return_value=mock_result):
            result = get_repo_identifier_from_local_repo(str(tmp_path))

        assert result == "owner/repo"

    def test_returns_empty_on_git_failure(self, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("qa_agents.utils.git_utils.subprocess.run", return_value=mock_result):
            result = get_repo_identifier_from_local_repo(str(tmp_path))

        assert result == ""

    def test_returns_empty_on_exception(self, tmp_path):
        with patch("qa_agents.utils.git_utils.subprocess.run", side_effect=OSError("no git")):
            result = get_repo_identifier_from_local_repo(str(tmp_path))

        assert result == ""
