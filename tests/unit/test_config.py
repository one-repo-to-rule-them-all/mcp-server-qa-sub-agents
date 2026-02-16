"""Unit tests for qa_agents.utils.config – env-based configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from qa_agents.utils.config import get_directory_from_env, get_github_token


@pytest.mark.unit
class TestGetDirectoryFromEnv:
    """Verify directory resolution from environment variables."""

    def test_returns_default_when_env_not_set(self, tmp_path):
        default = str(tmp_path / "default_dir")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST_DIR_VAR", None)
            result = get_directory_from_env("TEST_DIR_VAR", default)

        assert result == Path(default)
        assert result.exists()

    def test_returns_env_value_when_set(self, tmp_path):
        custom = str(tmp_path / "custom_dir")
        with patch.dict(os.environ, {"TEST_DIR_VAR": custom}):
            result = get_directory_from_env("TEST_DIR_VAR", "/fallback")

        assert result == Path(custom)
        assert result.exists()

    def test_creates_directory_if_missing(self, tmp_path):
        new_dir = str(tmp_path / "nested" / "new_dir")
        assert not Path(new_dir).exists()

        result = get_directory_from_env("MISSING_DIR", new_dir)

        assert result.exists()
        assert result.is_dir()


@pytest.mark.unit
class TestGetGithubToken:
    """Verify token resolution across multiple env var names."""

    def test_returns_github_token(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_abc123", "GH_TOKEN": "", "GITHUB_PAT": ""}):
            assert get_github_token() == "ghp_abc123"

    def test_falls_back_to_gh_token(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": "gh_fallback", "GITHUB_PAT": ""}):
            assert get_github_token() == "gh_fallback"

    def test_falls_back_to_github_pat(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": "", "GITHUB_PAT": "pat_last"}):
            assert get_github_token() == "pat_last"

    def test_returns_empty_when_none_set(self, clean_env):
        assert get_github_token() == ""

    def test_strips_whitespace(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "  ghp_spaced  ", "GH_TOKEN": "", "GITHUB_PAT": ""}):
            assert get_github_token() == "ghp_spaced"
