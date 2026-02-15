# Autonomous QA Council MCP Server

A production-oriented MCP server that runs a **multi-agent QA workflow** for Python/web repositories: clone, analyze, generate tests, execute tests, suggest repairs, and wire CI/CD.

## What this server does

The server exposes MCP tools powered by specialized agents:

- **Repository Agent**: clones or updates a target repo.
- **Analyzer Agent**: scans Python code with AST and surfaces test targets.
- **Generator Agent**: scaffolds unit tests (Python/React) and Playwright E2E tests.
- **Executor Agent**: runs pytest with coverage + HTML reporting.
- **Repair Agent**: classifies common failures and suggests fixes.
- **CI/CD Agent**: creates `.github/workflows/qa_testing.yml` and can dispatch it on GitHub.
- **Orchestrator Agent**: runs the end-to-end council flow.

## Data flow

```text
Repo URL
  ↓
clone_repository
  ↓
analyze_codebase
  ↓
generate_unit_tests / generate_e2e_tests
  ↓
execute_tests
  ↓
repair_failing_tests (if failures)
  ↓
generate_github_workflow (+ optional workflow_dispatch trigger)
```

## Available MCP tools

- `clone_repository(repo_url, branch="main")`
- `analyze_codebase(repo_path, file_pattern="*.py")`
- `generate_unit_tests(repo_path, target_file)`
- `generate_e2e_tests(repo_path, base_url, test_name="app")`
- `execute_tests(repo_path, test_path="")`
- `repair_failing_tests(repo_path, test_output)`
- `generate_github_workflow(repo_path, test_command="pytest", trigger_workflow="true", workflow_repo="one-repo-to-rule-them-all/media-collection-tracker", workflow_ref="main")`
- `create_test_fix_pr(repo_url, test_output, fixes)`
- `orchestrate_full_qa_cycle(repo_url, branch="main", base_url="")`

## Setup

### Prerequisites

- Python 3.11+
- Docker (if running containerized MCP deployment)
- Git
- Optional: `GITHUB_TOKEN` for private repos, PR creation, and workflow dispatch

### Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python qa_council_server.py
```

### Environment variables

- `WORKSPACE_DIR` (default: `/app/repos`)
- `TEST_RESULTS_DIR` (default: `/app/test_results`)
- `COVERAGE_DIR` (default: `/app/coverage`)
- `GITHUB_TOKEN` (recommended for GitHub API actions)

## CI/CD dispatch behavior

`generate_github_workflow` now supports two steps:

1. Writes `.github/workflows/qa_testing.yml` to the target repo path.
2. Optionally triggers GitHub Actions via `workflow_dispatch` using GitHub API.

Dispatch target resolution order:

1. `origin` remote of local repository (preferred)
2. `workflow_repo` argument fallback

If `GITHUB_TOKEN` is not configured, workflow file generation still succeeds and dispatch is returned as a warning.

## Best practices

- Use `orchestrate_full_qa_cycle` for first-pass automation; use individual tools for targeted iterations.
- Keep generated tests under `tests/unit` and `tests/e2e` and review before merge.
- Configure branch protection and required status checks after enabling the generated workflow.
- Keep `GITHUB_TOKEN` scoped minimally (repo/workflow permissions only).

## Development checks

```bash
pytest tests/unit -q
```

## License

Internal project / repository policy applies.
