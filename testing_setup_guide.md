# QA Testing Guide: Media Collection Tracker

## Prerequisites

- Docker (local image already built)
- Python 3.11+ (for native execution)
- GitHub Personal Access Token (for CI/CD workflow triggers)

---

## GitHub Token Setup

### 1. Create GitHub Personal Access Token

Navigate to: **Settings → Developer settings → Personal access tokens → Tokens (classic)**

**Required Scopes:**
- `repo` (full control of private repositories)
- `workflow` (update GitHub Action workflows)

### 2. Configure Token (Choose One Method)

#### Option A: Environment Variable (Recommended for Docker)
```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

#### Option B: Docker Secret Mount
```bash
# Create token file
echo "ghp_your_token_here" > ~/.github_token
chmod 600 ~/.github_token

# Mount when running container
docker run -v ~/.github_token:/run/secrets/github_token ...
```

#### Option C: Python Environment File
```bash
# Create .env file in project root
echo "GITHUB_TOKEN=ghp_your_token_here" > .env
```

---

## Execution Methods

### Method 1: Docker Execution (Recommended)

#### Single Command - Full QA Lifecycle
```bash
docker run --rm \
  -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
  -v "$(pwd)/results:/app/test_results" \
  -v "$(pwd)/coverage:/app/coverage" \
  your-qa-image:latest \
  python -c "
from qa_orchestrator import run_full_cycle
run_full_cycle(
    repo_url='https://github.com/one-repo-to-rule-them-all/media-collection-tracker',
    branch='main',
    base_url=''
)
"
```

#### Interactive Shell (For Debugging)
```bash
docker run -it --rm \
  -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
  -v "$(pwd)/results:/app/test_results" \
  -v "$(pwd)/coverage:/app/coverage" \
  your-qa-image:latest \
  /bin/bash
```

Then inside container:
```bash
python orchestrator_cli.py \
  --repo-url https://github.com/one-repo-to-rule-them-all/media-collection-tracker \
  --branch main
```

#### With MCP Gateway Server
```bash
docker run --rm \
  -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
  -v "$(pwd)/results:/app/test_results" \
  -v "$(pwd)/coverage:/app/coverage" \
  -p 8080:8080 \
  your-qa-image:latest \
  python -m qa_mcp_server
```

Then trigger via MCP client:
```python
import anthropic

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    tools=[{
        "name": "orchestrate_full_qa_cycle",
        "description": "Run full QA lifecycle",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_url": {"type": "string"},
                "branch": {"type": "string"},
                "base_url": {"type": "string"}
            }
        }
    }],
    messages=[{
        "role": "user",
        "content": "Run QA on media-collection-tracker"
    }]
)
```

---

### Method 2: Python Direct Execution

#### Installation
```bash
# Clone QA orchestrator repo
git clone https://github.com/your-org/qa-orchestrator.git
cd qa-orchestrator

# Install dependencies
pip install -r requirements.txt

# Configure GitHub token
export GITHUB_TOKEN="ghp_your_token_here"
```

#### Run Full Lifecycle
```bash
python orchestrator_cli.py \
  --repo-url https://github.com/one-repo-to-rule-them-all/media-collection-tracker \
  --branch main \
  --output-dir ./qa_results
```

#### Python Script Execution
```python
from qa_orchestrator import run_full_cycle
import os

# Ensure token is set
os.environ['GITHUB_TOKEN'] = 'ghp_your_token_here'

results = run_full_cycle(
    repo_url='https://github.com/one-repo-to-rule-them-all/media-collection-tracker',
    branch='main',
    base_url='',  # Optional: for E2E tests
    output_dir='./qa_results'
)

print(f"Tests passed: {results['executor']['passed']}")
print(f"Coverage: {results['executor']['coverage']}%")
print(f"Workflow generated: {results['cicd']['workflow_path']}")
```

---

## QA Lifecycle Stages

The orchestrator executes these agents in sequence:

### 1. Repository Agent
- Clones target repository
- Validates branch existence
- Location: `/app/repos/media-collection-tracker`

### 2. Inspector/Analyzer Agent
- Static code analysis
- Identifies testable components
- Detects classes, functions, complexity metrics

**Output:**
```json
{
  "files_analyzed": 10,
  "functions_found": 40,
  "classes_found": 4,
  "top_files": [...]
}
```

### 3. Test Generator Agent
- Creates unit tests (Python: pytest, JS/React: Vitest)
- Generates E2E tests (Playwright)
- Follows AAA pattern (Arrange, Act, Assert)

**Generated Files:**
- `tests/unit/test_main.py`
- `tests/unit/test_database_setup.py`
- `tests/unit/test_prestart.py`
- `tests/unit/App.test.tsx`

### 4. Executor Agent
- Runs pytest with coverage
- Generates HTML and XML reports
- Collects metrics

**Outputs:**
- `/app/test_results/report_<timestamp>.html`
- `/app/coverage/coverage_<timestamp>.xml`

### 5. Repairer Agent (Conditional)
- Analyzes test failures
- Suggests fixes via AI
- Can auto-commit repairs if configured

### 6. CI/CD Agent
- Generates GitHub Actions workflow
- Configures test matrix
- Triggers workflow dispatch (requires valid token)

**Generated File:**
`.github/workflows/qa_testing.yml`

---

## Output Artifacts

### File Structure
```
qa_results/
├── test_results/
│   └── report_20260216_001018.html
├── coverage/
│   ├── coverage_20260216_001018.xml
│   └── htmlcov/
│       └── index.html
├── logs/
│   ├── repository_agent.log
│   ├── inspector_agent.log
│   ├── generator_agent.log
│   ├── executor_agent.log
│   ├── repairer_agent.log
│   └── cicd_agent.log
└── generated_tests/
    └── tests/unit/
```

### Accessing Reports

#### Docker Volume Mount
```bash
# View HTML coverage report
open ./coverage/htmlcov/index.html

# View pytest report
open ./results/report_<timestamp>.html
```

#### Inside Container
```bash
docker exec -it <container_id> cat /app/test_results/report_*.html
```

---

## Common Issues & Troubleshooting

### Issue 1: No Tests Collected
**Symptom:** `collected 0 tests`

**Causes:**
1. Generated tests not in pytest discovery path
2. Import errors in test files
3. Missing `__init__.py` in test directories

**Fix:**
```bash
# Verify test discovery
docker run --rm your-qa-image pytest --collect-only

# Check imports
docker run --rm your-qa-image python -c "import tests.unit.test_main"

# Validate pytest config
docker run --rm your-qa-image cat pytest.ini
```

### Issue 2: GitHub Workflow Dispatch Failed (401)
**Symptom:** `401 Unauthorized: invalid GitHub token`

**Fix:**
```bash
# Verify token scopes
curl -H "Authorization: token ${GITHUB_TOKEN}" \
  https://api.github.com/user

# Regenerate token with correct scopes:
# - repo (full control)
# - workflow (update workflows)
```

### Issue 3: Coverage Report Empty
**Symptom:** Coverage shows N/A%

**Fix:**
```bash
# Ensure .coveragerc exists
cat > .coveragerc << EOF
[run]
source = backend,database,prestart
omit = tests/*,venv/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
EOF

# Run with coverage explicitly
pytest --cov=backend --cov=database --cov-report=html --cov-report=xml
```

### Issue 4: Import Errors in Generated Tests
**Symptom:** `ModuleNotFoundError: No module named 'backend'`

**Fix:**
```bash
# Add src to PYTHONPATH
export PYTHONPATH=/app/repos/media-collection-tracker:$PYTHONPATH

# Or install in editable mode
pip install -e /app/repos/media-collection-tracker
```

---

## Advanced Configuration

### Custom Test Generation Patterns
```python
# In orchestrator config
QA_CONFIG = {
    "generator": {
        "test_framework": "pytest",
        "mock_strategy": "unittest.mock",
        "coverage_threshold": 80,
        "test_patterns": {
            "unit": "tests/unit/test_{module}.py",
            "integration": "tests/integration/test_{module}_integration.py",
            "e2e": "tests/e2e/test_{feature}_flow.py"
        }
    }
}
```

### CI/CD Matrix Testing
Generated workflow includes:
```yaml
strategy:
  matrix:
    python-version: [3.9, 3.10, 3.11]
    os: [ubuntu-latest, macos-latest]
```

### Parallel Execution
```bash
# Docker with pytest-xdist
docker run --rm \
  -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
  your-qa-image \
  pytest -n auto tests/
```

---

## Performance Benchmarks

| Stage | Expected Duration | Memory Usage |
|-------|------------------|--------------|
| Repository Clone | 5-10s | ~50MB |
| Code Analysis | 2-5s | ~100MB |
| Test Generation | 10-30s | ~200MB |
| Test Execution | 15-60s | ~300MB |
| Workflow Generation | 1-3s | ~50MB |
| **Total** | **~60-120s** | **~500MB peak** |

---

## Security Considerations

1. **Never commit tokens to git**
   ```bash
   echo ".env" >> .gitignore
   echo ".github_token" >> .gitignore
   ```

2. **Use GitHub Actions secrets for CI/CD**
   ```yaml
   env:
     GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
   ```

3. **Rotate tokens regularly**
   - Set expiration (max 90 days recommended)
   - Revoke after project completion

4. **Limit token scope**
   - Only grant required permissions
   - Use fine-grained tokens when possible

---

## Quick Reference Commands

```bash
# Full cycle (Docker)
docker run --rm -e GITHUB_TOKEN=$GITHUB_TOKEN \
  -v $(pwd)/results:/app/test_results \
  mcp-server-qa-sub-agents:latest 
  python qa_council_server.py \
  --repo-url https://github.com/one-repo-to-rule-them-all/media-collection-tracker

# Full cycle (Python)
python qa_council_server.py \
  --repo-url https://github.com/one-repo-to-rule-them-all/media-collection-tracker \
  --branch main

# View logs
docker logs <container_id>

# Extract results
docker cp <container_id>:/app/test_results ./results
docker cp <container_id>:/app/coverage ./coverage

# Cleanup
docker system prune -a --volumes
```

---

## Support & Debugging

### Enable Verbose Logging
```bash
# Docker
docker run --rm -e LOG_LEVEL=DEBUG qa-image ...

# Python
python orchestrator_cli.py --log-level DEBUG ...
```

### Inspect Generated Tests
```bash
# View test file
docker exec <container_id> cat /app/repos/media-collection-tracker/tests/unit/test_main.py

# Run specific test
docker exec <container_id> pytest tests/unit/test_main.py::TestMediaAPI::test_health_check -v
```

### Agent-Specific Execution
```python
from qa_orchestrator.agents import GeneratorAgent

agent = GeneratorAgent()
agent.generate_tests(
    repo_path='/app/repos/media-collection-tracker',
    target_file='backend/main.py'
)
```

---

## Next Steps

1. **First Run:** Execute full cycle and review generated tests
2. **Review Reports:** Check coverage thresholds and test quality
3. **Iterate:** Add custom test patterns or edge cases
4. **CI Integration:** Enable workflow in GitHub Actions
5. **Monitor:** Set up alerts for test failures in production

For issues or enhancements, submit to the QA orchestrator repository.



```bash

$ MSYS_NO_PATHCONV=1 docker run -it   -e GITHUB_TOKEN="${GITHUB_TOKEN}"   -v "$(pwd)/results:/app/test_results"   -v "$(pwd)/coverage:/app/coverage"   mcp-server-qa-sub-agents:latest   /bin/bash


 python -c "import qa_agents; print(dir(qa_agents))"

 python -c "
import asyncio
import sys
sys.path.insert(0, '/app')
from qa_council_server import orchestrate_full_qa_cycle

async def run():
    result = await orchestrate_full_qa_cycle(
        repo_url='https://github.com/one-repo-to-rule-them-all/media-collection-tracker',
        branch='main',
        base_url=''
    )
    print(result)

asyncio.run(run())
"
```
