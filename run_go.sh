#!/bin/bash

# --- 2. BUILD ---
echo "🔨 Building image..."
docker build -t mcp-server-qa-sub-agents:latest .

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

# --- 3. RUN ---
echo "🚀 Starting container and running QA cycle..."

# We use -i (not -it) if running a script automatically to avoid TTY issues in some CI/Bash envs
# MSYS_NO_PATHCONV=1 handles Windows/Git Bash path mapping
MSYS_NO_PATHCONV=1 docker run --rm \
  -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
  -v "$(pwd)/results:/app/test_results" \
  -v "$(pwd)/coverage:/app/coverage" \
  mcp-server-qa-sub-agents:latest \
  /bin/bash 
  python -c "
import asyncio
import sys
import os

# Ensure /app is in path
sys.path.insert(0, '/app')

try:
    from qa_council_server import orchestrate_full_qa_cycle
    
    async def run():
        print('--- Starting Orchestration ---')
        result = await orchestrate_full_qa_cycle(
            repo_url='https://github.com/one-repo-to-rule-them-all/media-collection-tracker',
            branch='main',
            base_url=''
        )
        print('\n--- Result ---')
        print(result)

    asyncio.run(run())
except ImportError as e:
    print(f'❌ Import Error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Runtime Error: {e}')
    sys.exit(1)
"
