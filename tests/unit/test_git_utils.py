from qa_agents.utils.git_utils import (
    build_git_clone_url,
    parse_github_repo_identifier,
    sanitize_repo_name,
)


def test_sanitize_repo_name_strips_git_suffix():
    assert sanitize_repo_name("https://github.com/org/my-repo.git") == "my-repo"


def test_build_git_clone_url_injects_token_for_https():
    secured = build_git_clone_url("https://github.com/org/repo.git", "ghp_token")
    assert secured == "https://ghp_token@github.com/org/repo.git"


def test_parse_github_repo_identifier_supports_ssh_and_https():
    assert parse_github_repo_identifier("git@github.com:owner/repo.git") == "owner/repo"
    assert parse_github_repo_identifier("https://github.com/owner/repo") == "owner/repo"
