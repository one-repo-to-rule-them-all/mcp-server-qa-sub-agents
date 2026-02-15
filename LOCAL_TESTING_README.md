# QA Council MCP Server — Local Testing Guide

This guide walks you through local setup **from cloning the repo** to running and testing the QA Council MCP server.

It includes both options:

1. **Run directly with Python**
2. **Run inside Docker container**

It also explains exactly where to place your `GITHUB_TOKEN` for local use.

---

## 1) Clone the repository

```bash
git clone <YOUR_REPO_URL>
cd mcp-server-qa-sub-agents
```

Optional: check your current branch.

```bash
git branch
```

---

## 2) Configure environment variables (including GitHub token)

The server and agents read `GITHUB_TOKEN` from environment variables.

### Option A — Quick shell export (recommended for local dev)

```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

To verify it is set:

```bash
echo "$GITHUB_TOKEN"
```

> Tip: Keep your token out of shell history by running:
>
> ```bash
> read -s GITHUB_TOKEN
> export GITHUB_TOKEN
> ```

### Option B — `.env` file (recommended for repeat use)

Create a local file named `.env` (do **not** commit it):

```bash
GITHUB_TOKEN=ghp_your_token_here
```

If you run with Python directly, load `.env` into your shell before starting:

```bash
set -a
source .env
set +a
```

If you run with Docker, pass the env file with:

```bash
docker run --env-file .env ...
```

---

## 3) Run locally with Python

### 3.1 Create and activate virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3.2 Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.3 (Optional) Install Playwright browser binaries for e2e tests

If you plan to run e2e Playwright tests locally:

```bash
playwright install chromium
```

### 3.4 Start the MCP server

```bash
python qa_council_server.py
```

The server runs using stdio transport, so normally this is launched by your MCP client.

---

## 4) Run with Docker

### 4.1 Build image

```bash
docker build -t qa-council-mcp:local .
```

### 4.2 Run container

```bash
docker run --rm -it \
  --name qa-council-mcp \
  --env-file .env \
  -v "$(pwd)":/workspace \
  qa-council-mcp:local
```

If you do not use `.env`, pass token directly:

```bash
docker run --rm -it \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  qa-council-mcp:local
```

---

## 5) Verify setup quickly

### 5.1 Syntax check

```bash
python -m py_compile qa_council_server.py qa_agents/*.py
```

### 5.2 Run tests

```bash
pytest -q
```

If Playwright browser binaries are missing, e2e tests may fail until you run:

```bash
playwright install chromium
```

---

## 6) Example local workflow

1. Start server (Python or Docker).
2. From MCP client, call:
   - `clone_repository`
   - `analyze_codebase`
   - `generate_unit_tests`
   - `execute_tests`
3. If failures are found:
   - call `repair_failing_tests`
   - optionally call `create_test_fix_pr` (requires `GITHUB_TOKEN`).

---

## 7) Where to put `GITHUB_TOKEN` (summary)

- **Python run:** shell export (`export GITHUB_TOKEN=...`) or load from `.env` before starting.
- **Docker run:** pass `--env-file .env` or `-e GITHUB_TOKEN=...`.
- **Do not hardcode token in code.**
- **Do not commit `.env`.**

---

## 8) Troubleshooting

### `GITHUB_TOKEN not configured`

- Confirm variable exists in process environment:

```bash
python -c "import os; print(bool(os.getenv('GITHUB_TOKEN')))"
```

### Playwright errors about missing executable

- Install browsers:

```bash
playwright install chromium
```

### Git clone/pull failures in agent output

- Check token permissions and repository URL access.
- Confirm branch exists.

---

## 9) Security notes

- Prefer a fine-grained GitHub PAT with minimal required scopes.
- Rotate token periodically.
- Never commit token to repository files.
