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
  mcp-server-qa-sub-agents:latest \
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
  mcp-server-qa-sub-agents:latest \
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
  mcp-server-qa-sub-agentse:latest \
  python -m qa_council_server.py
```


### Method 2: Python Direct Execution

#### Installation
```bash
# Clone QA sub agent MCP server repo
git clone https://github.com/one-repo-to-rule-them-all/mcp-server-qa-sub-agents.git
cd mcp-server-qa-sub-agents

# Install dependencies
pip install -r requirements.txt

# Configure GitHub token
export GITHUB_TOKEN="ghp_your_token_here"
```

#### Run Full Lifecycle
```bash
python qa_council_server.py \
  --repo-url https://github.com/one-repo-to-rule-them-all/media-collection-tracker \
  --branch main \
  --output-dir ./qa_results
```


## Common Issues & Troubleshooting

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

```bash

run 
chmod +x run_qa.sh
./run_go.sh

docker build -t mcp-server-qa-sub-agents:latest .

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

