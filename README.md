# QA Council MCP Server - Professional Documentation

## 📋 Executive Summary

A production-ready autonomous QA testing system implementing a "Council of Agents" architecture for automated test generation, execution, analysis, and repair. Designed for enterprise-grade continuous integration workflows.

### Key Capabilities

- **Multi-Agent Architecture**: 6 specialized agents working in concert
- **Full Lifecycle Automation**: Clone → Analyze → Generate → Execute → Repair → Deploy
- **GitHub Integration**: Automatic PR creation with fix recommendations
- **Coverage Analysis**: Comprehensive test coverage reporting
- **CI/CD Ready**: GitHub Actions workflows included

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude (Orchestrator)                     │
│              [Can call agents individually or               │
│               use orchestrate_full_qa_cycle]                │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Agent 1    │  │   Agent 2    │  │   Agent 3    │
│ Repository   │  │  Inspector   │  │  Generator   │
└──────────────┘  └──────────────┘  └──────────────┘
        │                │                │
        ▼                ▼                ▼
   [Git Ops]      [AST Parse]      [Test Creation]
        │                │                │
        └────────────────┼────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Agent 4    │  │   Agent 5    │  │   Agent 6    │
│  Executor    │  │  Repairer    │  │    CI/CD     │
└──────────────┘  └──────────────┘  └──────────────┘
        │                │                │
        ▼                ▼                ▼
 [pytest/PW]     [Fix Analysis]   [GH Actions]
```

### Agent Responsibilities

| Agent | Purpose | Input | Output | Tools Used |
|-------|---------|-------|--------|------------|
| **Repository** | Source code management | Repo URL | Cloned code | Git |
| **Inspector** | Code analysis | File paths | Component list | AST, os.walk |
| **Generator** | Test creation | Components | Test files | Templates |
| **Executor** | Test execution | Test files | Results + coverage | pytest, Playwright |
| **Repairer** | Failure analysis | Test output | Fix suggestions | Pattern matching |
| **CI/CD** | Pipeline generation | Config | Workflow files | YAML generation |

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Version | Required | Purpose |
|-------------|---------|----------|---------|
| Docker Desktop | 20+ | Yes | Container runtime |
| Docker MCP Plugin | Latest | Yes | MCP integration |
| Python | 3.9+ | Local testing | Development |
| GitHub Token | N/A | Optional | PR creation |

### Installation (5 Minutes)

```bash
# 1. Create project directory
mkdir qa-council-mcp-server
cd qa-council-mcp-server

# 2. Save the files (provided separately)
# - Dockerfile
# - requirements.txt
# - qa_council_server.py (FIXED VERSION)
# - readme.txt (this file)
# - CLAUDE.md

# 3. Build Docker image
docker build -t qa-council-mcp-server:latest .

# Expected time: 5-10 minutes (Playwright browsers are large)

# 4. Configure GitHub token (optional, for PR creation)
docker mcp secret set GITHUB_TOKEN="ghp_your_github_token_here"

# 5. Create MCP catalog entry
mkdir -p ~/.docker/mcp/catalogs
nano ~/.docker/mcp/catalogs/custom.yaml
```

Add to `custom.yaml`:

```yaml
version: 2
name: custom
displayName: Custom MCP Servers
registry:
  qa-council:
    description: "Autonomous QA testing with multi-agent architecture"
    title: "QA Testing Council"
    type: server
    dateAdded: "2026-02-14T00:00:00Z"
    image: qa-council-mcp-server:latest
    ref: ""
    tools:
      - name: clone_repository
      - name: analyze_codebase
      - name: generate_unit_tests
      - name: generate_e2e_tests
      - name: execute_tests
      - name: repair_failing_tests
      - name: generate_github_workflow
      - name: create_test_fix_pr
      - name: generate_council_configuration
      - name: orchestrate_full_qa_cycle
    secrets:
      - name: GITHUB_TOKEN
        env: GITHUB_TOKEN
        example: ghp_xxxxxxxxxxxx
    metadata:
      category: automation
      tags: [testing, qa, ci-cd, automation]
      license: MIT
      owner: local
```

```bash
# 6. Update registry
nano ~/.docker/mcp/registry.yaml
```

Add under `registry:` key:

```yaml
registry:
  qa-council:
    ref: ""
```

```bash
# 7. Configure Claude Desktop
# Edit: ~/Library/Application Support/Claude/claude_desktop_config.json (macOS)
#   or: %APPDATA%\Claude\claude_desktop_config.json (Windows)
#   or: ~/.config/Claude/claude_desktop_config.json (Linux)
```

Add custom catalog to args:

```json
{
  "mcpServers": {
    "mcp-toolkit-gateway": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", "/Users/YOUR_USERNAME/.docker/mcp:/mcp",
        "docker/mcp-gateway",
        "--catalog=/mcp/catalogs/docker-mcp.yaml",
        "--catalog=/mcp/catalogs/custom.yaml",
        "--config=/mcp/config.yaml",
        "--registry=/mcp/registry.yaml",
        "--tools-config=/mcp/tools.yaml",
        "--transport=stdio"
      ]
    }
  }
}
```

```bash
# 8. Restart Claude Desktop
# Quit completely and relaunch

# 9. Verify installation
docker mcp server list | grep qa-council
```

Expected output:
```
qa-council    qa-council-mcp-server:latest    Running
```

---

## 💼 Usage Guide for Lead QA Engineers

### Individual Agent Usage


#### Agent 7: Council Configuration
```
You: "Generate a Council-of-Sub-Agents configuration for this repo"

Claude calls: generate_council_configuration(repo_path="/app/repos/api-service")

Result: .qa-council/council-config.yml + .github/workflows/qa_council_autofix.yml
```

#### Agent 1: Repository Management
```
You: "Clone https://github.com/company/api-service for testing"

Claude calls: clone_repository(repo_url="...", branch="main")

Result: Code ready at /app/repos/api-service
```

#### Agent 2: Code Analysis
```
You: "Analyze the codebase structure and identify test targets"

Claude calls: analyze_codebase(repo_path="/app/repos/api-service")

Result: List of functions, classes, complexity metrics
```

#### Agent 3: Test Generation
```
You: "Generate unit tests for api/routes.py"

Claude calls: generate_unit_tests(
    repo_path="/app/repos/api-service",
    target_file="api/routes.py"
)

Result: tests/unit/test_routes.py created with test cases
```

#### Agent 4: Test Execution
```
You: "Run all tests with coverage"

Claude calls: execute_tests(repo_path="/app/repos/api-service")

Result: Pass/fail counts, coverage percentage, report files
```

#### Agent 5: Failure Analysis
```
You: "Analyze the test failures and suggest fixes"

Claude calls: repair_failing_tests(
    repo_path="/app/repos/api-service",
    test_output="<previous test output>"
)

Result: Categorized failures with specific fix suggestions
```

#### Agent 6: CI/CD Generation
```
You: "Create GitHub Actions workflow for automated testing"

Claude calls: generate_github_workflow(
    repo_path="/app/repos/api-service",
    test_command="pytest --cov=api"
)

Result: .github/workflows/qa_testing.yml created
```

### Full Lifecycle Automation

```
You: "Run complete QA cycle on https://github.com/company/api-service"

Claude calls: orchestrate_full_qa_cycle(
    repo_url="https://github.com/company/api-service",
    branch="develop",
    base_url="http://localhost:8000"
)

Result: All 6 agents execute in sequence:
  ✅ Repository Agent → Code cloned
  ✅ Inspector Agent → 15 files, 47 functions analyzed
  ✅ Generator Agent → 23 unit tests, 8 E2E tests created
  ✅ Executor Agent → Tests run, 82% coverage
  ✅ Repairer Agent → 3 failures analyzed, fixes suggested
  ✅ CI/CD Agent → GitHub workflow generated
```

### Advanced: PR Creation

```
You: "Create a PR with the recommended test fixes"

Claude calls: create_test_fix_pr(
    repo_url="https://github.com/company/api-service",
    test_output="<test results>",
    fixes='[{"file": "tests/test_api.py", "content": "..."}]'
)

Result: Pull request created with:
  - Fix branch: qa-council/auto-fix-20260214-143052
  - PR title: 🤖 Automated Test Fixes from QA Council
  - Detailed analysis in PR description
```

---

## 🧪 Local Testing (Without Docker)

### Environment Setup

```bash
# 1. Create virtual environment
python3 -m venv venv

# 2. Activate
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers
playwright install chromium
playwright install-deps  # Linux only

# 5. Verify installation
python -c "import mcp; print('MCP installed')"
playwright --version
```

### Running the Server Locally

```bash
# Set environment variables
export GITHUB_TOKEN="ghp_your_token"  # Optional
export WORKSPACE_DIR="/tmp/qa-repos"
export TEST_RESULTS_DIR="/tmp/qa-results"
export COVERAGE_DIR="/tmp/qa-coverage"

# Run server
python qa_council_server.py
```

### Testing Individual Functions

```python
# test_agents.py
import asyncio
from qa_council_server import (
    clone_repository,
    analyze_codebase,
    generate_unit_tests
)

async def test_repository_agent():
    result = await clone_repository(
        repo_url="https://github.com/test/repo",
        branch="main"
    )
    print(result)
    assert "✅" in result

async def test_inspector_agent():
    result = await analyze_codebase(
        repo_path="/app/repos/test-repo",
        file_pattern="*.py"
    )
    print(result)
    assert "📊" in result

if __name__ == "__main__":
    asyncio.run(test_repository_agent())
    asyncio.run(test_inspector_agent())
```

Run tests:
```bash
python test_agents.py
```

---

## 📊 Test Coverage Strategy

### Coverage Goals by Component

| Component | Target | Rationale |
|-----------|--------|-----------|
| API Endpoints | 85%+ | Critical user-facing code |
| Database Layer | 90%+ | Data integrity crucial |
| Business Logic | 90%+ | Core functionality |
| Utilities | 75%+ | Supporting code |
| UI Components | 70%+ | Visual testing complements |

### Measuring Coverage

```bash
# Generate coverage report
pytest --cov=. --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html

# Check if meets threshold
pytest --cov=. --cov-fail-under=85
```

### Coverage Report Interpretation

```
Name                 Stmts   Miss  Cover   Missing
--------------------------------------------------
api/routes.py          156     22    86%   45-47, 89-92
database/models.py      89      8    91%   145-152
utils/helpers.py        45     12    73%   23-34
--------------------------------------------------
TOTAL                  290     42    85%
```

**Analysis**:
- ✅ API routes: Acceptable (86% > 85% target)
- ✅ Database: Excellent (91% > 90% target)
- ⚠️ Utilities: Below target (73% < 75% target) - needs attention

---

## 🔧 Troubleshooting

### Issue: "Path does not exist" errors

**Symptoms**: Agent tools fail with path not found
**Cause**: Docker container isolation or permissions
**Solution**:
```bash
# Verify repository was cloned
docker exec <container_id> ls -la /app/repos

# Check permissions
docker exec <container_id> ls -la /app/repos/<repo_name>

# Try using the fixed version (v2.0)
# Includes improved path verification
```

### Issue: Agents not executing in orchestrator

**Symptoms**: `orchestrate_full_qa_cycle` shows minimal output
**Cause**: Using old version that doesn't call sub-agents
**Solution**:
```bash
# Upgrade to fixed version
cp qa_council_server_fixed.py qa_council_server.py
docker build -t qa-council-mcp-server:latest .
```

### Issue: PR creation fails

**Symptoms**: "GitHub token not configured" error
**Cause**: GITHUB_TOKEN not set
**Solution**:
```bash
# Set token
docker mcp secret set GITHUB_TOKEN="ghp_xxxxxxxxxxxx"

# Verify
docker mcp secret list

# Rebuild container to pick up secret
docker mcp reload
```

### Issue: Playwright tests fail

**Symptoms**: "Executable doesn't exist" errors
**Cause**: Browsers not installed
**Solution**:
```bash
# Rebuild image (browsers install during build)
docker build -t qa-council-mcp-server:latest .

# Or install manually in running container
docker exec <container_id> playwright install chromium
```

### Issue: Tests timeout

**Symptoms**: "Test execution timed out" (300s timeout)
**Cause**: Large test suite or slow tests
**Solution**:
```python
# Edit qa_council_server.py
# In run_pytest function, increase timeout:
timeout=600  # 10 minutes instead of 5
```

---

## 🏢 Enterprise Integration

### CI/CD Pipeline Integration

#### GitHub Actions (Included)
```yaml
# Automatically generated by Agent 6
# Features: test execution, coverage, PR creation
# Location: .github/workflows/qa_testing.yml
```

#### GitLab CI
```yaml
# .gitlab-ci.yml
test:
  image: python:3.11
  script:
    - pip install -r requirements.txt
    - pytest --cov=. --cov-report=xml
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
```

#### Jenkins
```groovy
// Jenkinsfile
pipeline {
    agent { docker { image 'python:3.11' } }
    stages {
        stage('Test') {
            steps {
                sh 'pip install -r requirements.txt'
                sh 'pytest --cov=. --junitxml=results.xml'
            }
        }
    }
    post {
        always {
            junit 'results.xml'
        }
    }
}
```

### Slack/Teams Notifications

Add to GitHub Actions workflow:

```yaml
- name: Notify Slack
  if: always()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    text: |
      QA Council Test Results:
      Passed: ${{ steps.test.outputs.passed }}
      Failed: ${{ steps.test.outputs.failed }}
      Coverage: ${{ steps.test.outputs.coverage }}%
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### Jira Integration

```python
# Create Jira ticket for test failures
@mcp.tool()
async def create_jira_ticket(summary: str, description: str) -> str:
    """Create Jira ticket for test failures."""
    # Implementation using Jira API
```

---

## 📈 Metrics and Reporting

### Key Metrics Tracked

1. **Test Success Rate**: % of passing tests over time
2. **Coverage Trend**: Coverage percentage changes per commit
3. **Test Execution Time**: Duration of test suite
4. **Failure Categories**: Types of test failures
5. **Fix Time**: Time from failure detection to fix merge

### Dashboards

Integrate with:
- **Codecov**: Coverage visualization
- **SonarQube**: Code quality + test coverage
- **TestRail**: Test management
- **Grafana**: Custom metrics dashboards

---

## 🔐 Security Considerations

### Secrets Management

```bash
# GOOD: Use Docker secrets
docker mcp secret set GITHUB_TOKEN="token"
docker mcp secret set API_KEY="key"

# BAD: Hardcode in files
GITHUB_TOKEN = "ghp_xxxx"  # Never do this!
```

### Code Scanning

The generated GitHub Actions workflow includes:
- Dependency scanning (automatically enabled)
- SAST scanning (optional, add CodeQL)
- Secret scanning (GitHub native)

### Access Control

```yaml
# Limit workflow permissions
permissions:
  contents: read
  pull-requests: write
  issues: write
```

---

## 🎓 Best Practices

### 1. Test Organization
```
tests/
├── unit/           # Fast, isolated tests
├── integration/    # Component interaction tests
├── e2e/            # Full user workflow tests
└── performance/    # Load and stress tests
```

### 2. Test Naming
```python
# GOOD
def test_user_login_with_valid_credentials():
    pass

# BAD
def test1():
    pass
```

### 3. Fixture Usage
```python
@pytest.fixture(scope="session")
def db_connection():
    """Reuse database connection across tests."""
    conn = create_connection()
    yield conn
    conn.close()
```

### 4. Coverage Targets
- Start with 70% overall coverage
- Increase gradually to 85%+
- Focus on critical paths first

### 5. Test Maintenance
- Review test failures weekly
- Refactor flaky tests immediately
- Archive obsolete tests

---

## 📞 Support and Contribution

### Getting Help

1. Check this README first
2. Review UPGRADE_GUIDE.md for known issues
3. Check Docker logs: `docker logs <container_id>`
4. Review test output in artifacts

### Contributing

To improve the QA Council system:

1. Fork and create feature branch
2. Add tests for new functionality
3. Update documentation
4. Submit pull request

---

## 📝 Change Log

### v2.0 (2026-02-14) - Fixed Release
- ✅ Fixed file path resolution in Docker containers
- ✅ Fixed orchestrator to actually call sub-agents
- ✅ Added GitHub PR creation functionality
- ✅ Enhanced error messages and logging
- ✅ Improved GitHub Actions workflow
- ✅ Added comprehensive documentation

### v1.0 (2026-02-01) - Initial Release
- Initial multi-agent architecture
- Basic test generation and execution
- Coverage reporting
- GitHub Actions integration

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🙏 Acknowledgments

- Inspired by [OpenObserve's AI Agent Architecture](https://openobserve.ai/blog/autonomous-qa-testing-ai-agents-claude-code/)
- Built on Model Context Protocol (MCP)
- Powered by FastMCP framework
- Testing with pytest and Playwright

---

**Maintained by**: QA Engineering Team  
**Version**: 2.0-fixed  
**Status**: Production Ready  
**Last Updated**: February 14, 2026
