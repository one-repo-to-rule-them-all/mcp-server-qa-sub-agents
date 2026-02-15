# Autonomous QA Testing Council - Implementation Guide

## Overview

This MCP server implements a multi-agent autonomous testing system for Python applications. It follows the "Council of Sub-Agents" pattern where specialized agents collaborate to handle different aspects of the QA lifecycle.

## Project Structure

```
qa_council_server.py              # Slim MCP entry point (~130 lines, tool wrappers only)
Dockerfile                        # Docker build with agents/ and utils/ copied
requirements.txt                  # Python dependencies

agents/
    __init__.py                   # Package exports
    repository_agent.py           # Clone/update Git repositories
    analyzer_agent.py             # Enhanced AST analysis with NodeVisitor
    generator_agent.py            # Strategy-based test generation with mocking
    executor_agent.py             # pytest execution with coverage
    repair_agent.py               # Failure parsing and fix suggestions
    cicd_agent.py                 # GitHub Actions workflow + PR creation
    orchestrator_agent.py         # Dynamic coordination (no hardcoded targets)

utils/
    __init__.py                   # Package exports
    config.py                     # Shared config, logger factory, directory setup
    path_utils.py                 # Path sanitization and verification
    git_utils.py                  # Clone, branch, PR operations
```

### Dependency Flow (DAG — no circular imports)

```
qa_council_server.py
    ├── agents/repository_agent   → utils/config, utils/git_utils
    ├── agents/analyzer_agent     → utils/config, utils/path_utils
    ├── agents/generator_agent    → utils/config, utils/path_utils, agents/analyzer_agent
    ├── agents/executor_agent     → utils/config, utils/path_utils
    ├── agents/repair_agent       → utils/config
    ├── agents/cicd_agent         → utils/config, utils/path_utils, utils/git_utils
    └── agents/orchestrator_agent → utils/config, ALL other agents (lazy imports)
```

## Agent Responsibilities

### 1. Repository Agent (`agents/repository_agent.py`)
- **Purpose**: Source code management
- **Tool**: `clone_repository(repo_url, branch)`
- **Delegates to**: `utils/git_utils.clone_or_update_repo()`

### 2. Analyzer Agent (`agents/analyzer_agent.py`)
- **Purpose**: Rich AST-based code comprehension
- **Tool**: `analyze_codebase(repo_path)`
- **Returns**: `tuple[str, list[dict]]` — display report AND raw analysis data

#### Enhanced Analysis (per function)
- `calls` — list of function calls made
- `raises` — exceptions raised
- `has_return` — whether function returns a value
- `decorators`, `docstring`, `is_async`
- `complexity_indicators`:
  - `uses_file_io` — calls `open()`, `read_text`, etc.
  - `uses_subprocess` — calls `subprocess.*`
  - `uses_http` — calls `httpx.*`, `requests.*`
  - `uses_os` — calls `os.*`, `Path.*`
  - `has_try_except`, `has_conditionals`, `has_loops`

#### Enhanced Analysis (per class)
- `bases` — parent classes
- `has_init`, `init_args` — constructor details
- `class_variables` — class-level assignments
- `methods` — full function analysis for each method

### 3. Test Generator Agent (`agents/generator_agent.py`)
- **Purpose**: Generate real pytest tests with mocking
- **Tools**: `generate_unit_tests()`, `generate_e2e_tests()`

#### Mock Strategy Resolution
The generator examines `complexity_indicators` and `calls` from the analyzer to determine which mocks are needed:

| Code Pattern | Mock Strategy |
|---|---|
| `open()` | `@patch("builtins.open", new_callable=mock_open)` |
| `subprocess.run` | `@patch("module.subprocess.run")` with configurable returncode |
| `httpx.AsyncClient` | `@patch("module.httpx.AsyncClient")` with AsyncMock |
| `requests.*` | `@patch("module.requests")` |
| `os.path.exists` | `@patch("module.os.path.exists", return_value=True)` |

#### Generated Tests Per Function
1. `test_{name}_success` — happy path with valid inputs and mock assertions
2. `test_{name}_empty_input` — empty/missing first argument
3. `test_{name}_various_inputs` — `@pytest.mark.parametrize` edge cases
4. `test_{name}_error_handling` — trigger exception paths via mocks (if try/except)
5. `test_{name}_subprocess_timeout` / `_failure` (if uses subprocess)
6. `test_{name}_file_not_found` (if uses file I/O)
7. `test_{name}_http_error` (if uses HTTP)

#### Argument Heuristics
Infers test values from parameter names:
- `*path*`, `*file*` → `"/tmp/test_file.txt"`
- `*url*` → `"https://example.com/test"`
- `*name*` → `"test_value"`
- `*count*` → `10`
- `*flag*` → `True`
- `*data*` → `{"key": "value"}`
- `branch` → `"main"`

### 4. Executor Agent (`agents/executor_agent.py`)
- **Purpose**: Run tests and collect metrics
- **Tool**: `execute_tests(repo_path, test_path)`
- **Features**: pytest with coverage, 5-minute timeout

### 5. Repair Agent (`agents/repair_agent.py`)
- **Purpose**: Diagnose failures and suggest fixes
- **Tool**: `repair_failing_tests(repo_path, test_output)`
- **Patterns**: ImportError, AssertionError, FileNotFoundError, AttributeError, TypeError

### 6. CI/CD Agent (`agents/cicd_agent.py`)
- **Purpose**: Pipeline automation and PR creation
- **Tools**: `generate_github_workflow()`, `create_test_fix_pr()`
- **Features**: GitHub Actions YAML, Codecov, Playwright, artifact upload

### 7. Orchestrator Agent (`agents/orchestrator_agent.py`)
- **Purpose**: Coordinate full lifecycle with dynamic target selection
- **Tool**: `orchestrate_full_qa_cycle(repo_url, branch, base_url)`

#### Dynamic Target Selection
Replaces hardcoded file list. Scores files by:
- +2 per public function, +3 per class
- +1 per complexity indicator
- Excludes: `__init__.py`, `test_*`, migrations, setup files
- Returns top 10 files sorted by score

#### Pipeline Phases
1. Clone Repository
2. Analyze Codebase (rich AST)
3. Select Test Targets (dynamic scoring)
4. Generate Tests (per target)
5. Execute Tests
6. Repair Analysis (if failures)
7. CI/CD Workflow Generation

## Configuration

### Environment Variables
- `GITHUB_TOKEN`: GitHub personal access token (optional)
- `WORKSPACE_DIR`: Repository clone location (default: `/app/repos`)
- `TEST_RESULTS_DIR`: Test output location (default: `/app/test_results`)
- `COVERAGE_DIR`: Coverage report location (default: `/app/coverage`)

### Docker Volumes
- `/app/repos`: Persistent repository storage
- `/app/test_results`: Test execution results
- `/app/coverage`: Coverage reports

## Usage

### Docker Build & Run
```bash
docker build -t qa-council .
docker run --rm -i qa-council
```

### MCP Tool Examples
```bash
# Clone a repository
echo '{"method":"tools/call","params":{"name":"clone_repository","arguments":{"repo_url":"https://github.com/user/repo"}}}' | python qa_council_server.py

# Analyze codebase
echo '{"method":"tools/call","params":{"name":"analyze_codebase","arguments":{"repo_path":"/app/repos/myrepo"}}}' | python qa_council_server.py

# Generate tests (single file)
echo '{"method":"tools/call","params":{"name":"generate_unit_tests","arguments":{"repo_path":"/app/repos/myrepo","target_file":"main.py"}}}' | python qa_council_server.py

# Full orchestration
echo '{"method":"tools/call","params":{"name":"orchestrate_full_qa_cycle","arguments":{"repo_url":"https://github.com/user/repo"}}}' | python qa_council_server.py
```

### Import Verification
```bash
python -c "from agents import *; from utils import *; print('All imports OK')"
```

## Error Handling Strategy

1. **Input Validation**: All agents check parameters before execution
2. **Graceful Degradation**: Return partial results on non-critical errors
3. **Comprehensive Logging**: stderr logs via `utils.config.get_logger()`
4. **Recovery Suggestions**: Repair agent provides actionable fixes

## References

- [Autonomous QA Testing with AI Agents](https://openobserve.ai/blog/autonomous-qa-testing-ai-agents-claude-code/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [pytest Documentation](https://docs.pytest.org/)
- [Playwright Python Documentation](https://playwright.dev/python/)
