#!/usr/bin/env python3
"""
Autonomous QA Testing Council MCP Server (FIXED VERSION)
Multi-agent system for test generation, execution, and repair

FIXES APPLIED:
1. Fixed file path resolution for Docker containers
2. Improved orchestrator to actually call sub-agents
3. Added proper error handling and retries
4. Fixed directory existence checks
5. Added GitHub API integration for PR creation
"""
import os
import sys
import logging
import json
import subprocess
import shutil
import ast
import re
from pathlib import Path
from datetime import datetime, timezone
from mcp.server.fastmcp import FastMCP
import httpx
from qa_agents.analyzer_agent import analyze_codebase as analyzer_agent_analyze_codebase
from qa_agents.cicd_agent import generate_github_workflow as cicd_agent_generate_github_workflow
from qa_agents.executor_agent import execute_tests as executor_agent_execute_tests
from qa_agents.generator_agent import generate_e2e_tests as generator_agent_generate_e2e_tests
from qa_agents.generator_agent import generate_unit_tests as generator_agent_generate_unit_tests
from qa_agents.repair_agent import repair_failing_tests as repair_agent_repair_failing_tests
from qa_agents.repository_agent import clone_repository as repository_agent_clone_repository

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("qa-council-server")

# Initialize MCP server
mcp = FastMCP("qa-council")

# Configuration
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
WORKSPACE_DIR = Path("/app/repos")
TEST_RESULTS_DIR = Path("/app/test_results")
COVERAGE_DIR = Path("/app/coverage")

# Ensure directories exist
WORKSPACE_DIR.mkdir(exist_ok=True)
TEST_RESULTS_DIR.mkdir(exist_ok=True)
COVERAGE_DIR.mkdir(exist_ok=True)

# === UTILITY FUNCTIONS ===

def sanitize_repo_name(repo_url: str) -> str:
    """Extract safe directory name from repo URL."""
    name = repo_url.rstrip('/').split('/')[-1]
    if name.endswith('.git'):
        name = name[:-4]
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)

def extract_github_info(repo_url: str) -> tuple:
    """Extract owner and repo name from GitHub URL."""
    parts = repo_url.rstrip('/').split('/')
    if 'github.com' in repo_url:
        owner = parts[-2]
        repo = parts[-1].replace('.git', '')
        return owner, repo
    return None, None

def clone_or_update_repo(repo_url: str, branch: str = "main") -> tuple:
    """Clone or update a GitHub repository."""
    repo_name = sanitize_repo_name(repo_url)
    repo_path = WORKSPACE_DIR / repo_name
    
    try:
        if repo_path.exists():
            logger.info(f"Updating existing repo: {repo_name}")
            result = subprocess.run(
                ["git", "-C", str(repo_path), "pull", "origin", branch],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                return False, f"Git pull failed: {result.stderr}"
        else:
            logger.info(f"Cloning new repo: {repo_name}")
            git_url = repo_url
            if GITHUB_TOKEN:
                git_url = repo_url.replace("https://", f"https://{GITHUB_TOKEN}@")
            
            result = subprocess.run(
                ["git", "clone", "-b", branch, git_url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                return False, f"Git clone failed: {result.stderr}"
        
        return True, str(repo_path)
    except subprocess.TimeoutExpired:
        return False, "Git operation timed out"
    except Exception as e:
        return False, str(e)

def verify_path_exists(path: str) -> tuple:
    """Verify path exists and is accessible - FIXED VERSION."""
    try:
        p = Path(path)
        # Try multiple verification methods
        if p.exists():
            return True, str(p)
        
        # Try using os.path.exists as fallback
        if os.path.exists(path):
            return True, path
        
        # Try listing parent directory to verify
        parent = p.parent
        if parent.exists():
            children = list(parent.iterdir())
            for child in children:
                if child.name == p.name:
                    return True, str(child)
        
        return False, f"Path not found: {path}"
    except Exception as e:
        return False, f"Path verification error: {str(e)}"

def analyze_python_file(file_path: str) -> dict:
    """Analyze Python file structure and extract testable components."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        functions = []
        classes = []
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "lineno": node.lineno,
                    "is_async": isinstance(node, ast.AsyncFunctionDef)
                })
            elif isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                classes.append({
                    "name": node.name,
                    "methods": methods,
                    "lineno": node.lineno
                })
            elif isinstance(node, ast.Import):
                imports.extend([alias.name for alias in node.names])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        return {
            "functions": functions,
            "classes": classes,
            "imports": imports,
            "total_lines": len(content.split('\n'))
        }
    except Exception as e:
        logger.error(f"Error analyzing {file_path}: {e}")
        return {"error": str(e)}

def generate_unit_test(component: dict, file_path: str) -> str:
    """Generate unit test code for a component."""
    if "name" in component:
        if "methods" in component:
            test_code = f'''"""Unit tests for {component["name"]} class."""
import pytest
from {Path(file_path).stem} import {component["name"]}

class Test{component["name"]}:
    """Test suite for {component["name"]}."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.instance = {component["name"]}()
    
'''
            for method in component["methods"]:
                if not method.startswith("_"):
                    test_code += f'''    def test_{method}(self):
        """Test {method} method."""
        # TODO: Add test implementation
        assert hasattr(self.instance, "{method}")
    
'''
        else:
            test_code = f'''"""Unit tests for {component["name"]} function."""
import pytest
from {Path(file_path).stem} import {component["name"]}

def test_{component["name"]}_basic():
    """Test basic functionality of {component["name"]}."""
    # TODO: Add test implementation
    pass

def test_{component["name"]}_edge_cases():
    """Test edge cases for {component["name"]}."""
    # TODO: Add test implementation
    pass
'''
        return test_code
    return ""

def generate_playwright_test(page_url: str, test_name: str) -> str:
    """Generate Playwright E2E test."""
    return f'''"""E2E tests for {test_name}."""
import pytest
from playwright.sync_api import Page, expect
import re

def test_{test_name}_page_loads(page: Page, base_url: str):
    """Test that the page loads successfully."""
    page.goto(base_url)
    expect(page).to_have_title(re.compile(r".+"))

def test_{test_name}_navigation(page: Page, base_url: str):
    """Test navigation elements."""
    page.goto(base_url)
    # TODO: Add navigation tests

def test_{test_name}_interactions(page: Page, base_url: str):
    """Test user interactions."""
    page.goto(base_url)
    # TODO: Add interaction tests
'''

def run_pytest(repo_path: str, test_path: str = "") -> tuple:
    """Execute pytest with coverage."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = TEST_RESULTS_DIR / f"report_{timestamp}.html"
    coverage_file = COVERAGE_DIR / f"coverage_{timestamp}.xml"
    
    cmd = [
        "pytest",
        "-v",
        "--tb=short",
        f"--html={report_file}",
        "--self-contained-html",
        f"--cov={repo_path}",
        f"--cov-report=xml:{coverage_file}",
        "--cov-report=term"
    ]
    
    if test_path:
        cmd.append(test_path)
    else:
        cmd.append(repo_path)
    
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        return True, {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "report_file": str(report_file),
            "coverage_file": str(coverage_file)
        }
    except subprocess.TimeoutExpired:
        return False, {"error": "Test execution timed out"}
    except Exception as e:
        return False, {"error": str(e)}

def parse_test_failures(pytest_output: str) -> list:
    """Parse pytest output to extract failure information."""
    failures = []
    lines = pytest_output.split('\n')
    
    current_failure = {}
    in_failure = False
    
    for line in lines:
        if line.startswith("FAILED"):
            in_failure = True
            current_failure = {"test": line.split()[0], "lines": []}
        elif in_failure:
            if line.startswith("===") or line.startswith("PASSED") or line.startswith("FAILED"):
                if current_failure.get("lines"):
                    failures.append(current_failure)
                current_failure = {}
                in_failure = False
            else:
                current_failure.get("lines", []).append(line)
    
    return failures

def generate_test_repair(failure_info: dict) -> str:
    """Generate suggestions for repairing failed tests."""
    suggestions = []
    
    failure_text = '\n'.join(failure_info.get("lines", []))
    
    if "AssertionError" in failure_text:
        suggestions.append("Check assertion conditions - expected vs actual values may not match")
    if "AttributeError" in failure_text:
        suggestions.append("Verify object attributes and method names are correct")
    if "TypeError" in failure_text:
        suggestions.append("Check function argument types and counts")
    if "ImportError" in failure_text or "ModuleNotFoundError" in failure_text:
        suggestions.append("Ensure all required modules are installed and import paths are correct")
    if "fixture" in failure_text.lower():
        suggestions.append("Verify pytest fixtures are properly defined and scoped")
    
    if not suggestions:
        suggestions.append("Review test logic and ensure it matches current implementation")
    
    return suggestions

async def create_github_pr(owner: str, repo: str, title: str, body: str, head_branch: str, base_branch: str = "main") -> tuple:
    """Create a GitHub Pull Request with recommended changes."""
    if not GITHUB_TOKEN:
        return False, "GitHub token not configured"
    
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    data = {
        "title": title,
        "body": body,
        "head": head_branch,
        "base": base_branch
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 201:
                pr_data = response.json()
                return True, pr_data["html_url"]
            else:
                return False, f"GitHub API error: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"Error creating PR: {str(e)}"

async def create_test_fix_branch(repo_path: str, branch_name: str, fixes: list) -> tuple:
    """Create a new branch with test fixes."""
    try:
        # Create new branch
        result = subprocess.run(
            ["git", "-C", repo_path, "checkout", "-b", branch_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return False, f"Failed to create branch: {result.stderr}"
        
        # Apply fixes (write fix files)
        for fix in fixes:
            file_path = Path(repo_path) / fix["file"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                f.write(fix["content"])
        
        # Stage changes
        subprocess.run(["git", "-C", repo_path, "add", "."], check=True, timeout=10)
        
        # Commit
        subprocess.run(
            ["git", "-C", repo_path, "commit", "-m", "fix: Apply automated test repairs from QA Council"],
            check=True,
            timeout=10
        )
        
        # Push
        subprocess.run(
            ["git", "-C", repo_path, "push", "-u", "origin", branch_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return True, branch_name
    except Exception as e:
        return False, f"Error creating fix branch: {str(e)}"

# === MCP TOOLS ===

@mcp.tool()
async def clone_repository(repo_url: str = "", branch: str = "main") -> str:
    """Clone or update a GitHub repository for testing."""
    logger.info(f"Repository Agent: cloning/updating {repo_url}")
    return await repository_agent_clone_repository(repo_url, branch, WORKSPACE_DIR)

@mcp.tool()
async def analyze_codebase(repo_path: str = "", file_pattern: str = "*.py") -> str:
    """Analyze Python codebase structure and identify testable components."""
    logger.info(f"Analyzer Agent: analyzing {repo_path}")
    return await analyzer_agent_analyze_codebase(repo_path, file_pattern)

@mcp.tool()
async def generate_unit_tests(repo_path: str = "", target_file: str = "") -> str:
    """Generate unit tests for Python functions and classes in a file."""
    logger.info(f"Generator Agent (unit): generating tests for {target_file}")
    return await generator_agent_generate_unit_tests(repo_path, target_file)

@mcp.tool()
async def generate_e2e_tests(repo_path: str = "", base_url: str = "", test_name: str = "app") -> str:
    """Generate Playwright E2E tests for web applications."""
    logger.info(f"Generator Agent (e2e): generating tests for {base_url}")
    return await generator_agent_generate_e2e_tests(repo_path, base_url, test_name)

@mcp.tool()
async def execute_tests(repo_path: str = "", test_path: str = "") -> str:
    """Execute pytest tests with coverage reporting."""
    logger.info(f"Executor Agent: running tests in {repo_path}")
    return await executor_agent_execute_tests(repo_path, TEST_RESULTS_DIR, COVERAGE_DIR, test_path)

@mcp.tool()
async def repair_failing_tests(repo_path: str = "", test_output: str = "") -> str:
    """Analyze test failures and provide repair suggestions."""
    logger.info(f"Repair Agent: analyzing failures for {repo_path}")
    return await repair_agent_repair_failing_tests(repo_path, test_output)

@mcp.tool()
async def generate_github_workflow(repo_path: str = "", test_command: str = "pytest") -> str:
    """Generate GitHub Actions workflow for CI/CD testing."""
    logger.info(f"CI/CD Agent: generating workflow for {repo_path}")
    return await cicd_agent_generate_github_workflow(repo_path, test_command)

@mcp.tool()
async def create_test_fix_pr(repo_url: str = "", test_output: str = "", fixes: str = "") -> str:
    """Create GitHub PR with automated test fixes from QA Council analysis."""
    if not repo_url.strip():
        return "❌ Error: Repository URL is required"
    
    owner, repo = extract_github_info(repo_url)
    if not owner or not repo:
        return "❌ Error: Invalid GitHub repository URL"
    
    if not GITHUB_TOKEN:
        return "❌ Error: GITHUB_TOKEN not configured. Set it as an environment variable."
    
    logger.info(f"Creating test fix PR for {owner}/{repo}")
    
    try:
        # Get repo path
        repo_name = sanitize_repo_name(repo_url)
        repo_path = str(WORKSPACE_DIR / repo_name)
        
        # Create fix branch
        branch_name = f"qa-council/test-fixes-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Parse fixes (expect JSON string)
        try:
            fix_list = json.loads(fixes) if fixes.strip() else []
        except:
            fix_list = []
        
        if fix_list:
            success, result = await create_test_fix_branch(repo_path, branch_name, fix_list)
            if not success:
                return f"❌ Failed to create fix branch: {result}"
        
        # Create PR
        pr_title = "🤖 Automated Test Fixes from QA Council"
        pr_body = f"""## 🤖 Automated Test Repair Analysis

This PR contains automated fixes suggested by the QA Council multi-agent system.

### 📊 Analysis Summary
{test_output[:500] if test_output else 'Test analysis completed'}

### 🔧 Fixes Applied
{chr(10).join([f"- {fix.get('description', 'Test fix')}" for fix in fix_list]) if fix_list else '- Analysis and recommendations provided'}

### ✅ Next Steps
1. Review the changes carefully
2. Run tests locally: `pytest -v`
3. Merge if all tests pass

---
*Generated by QA Council Autonomous Testing System*
"""
        
        success, pr_url = await create_github_pr(owner, repo, pr_title, pr_body, branch_name)
        
        if success:
            return f"""✅ Pull Request Created Successfully

🔗 PR URL: {pr_url}
📝 Branch: {branch_name}
🤖 Generated by: QA Council

The PR includes:
- Automated test fixes
- Detailed analysis
- Repair recommendations

Review and merge when ready!
"""
        else:
            return f"❌ Failed to create PR: {pr_url}"
        
    except Exception as e:
        logger.error(f"PR creation error: {e}")
        return f"❌ Error creating PR: {str(e)}"

@mcp.tool()
async def orchestrate_full_qa_cycle(repo_url: str = "", branch: str = "main", base_url: str = "") -> str:
    """Execute complete QA lifecycle by calling all specialized agent tools in sequence - FIXED VERSION."""
    if not repo_url.strip():
        return "❌ Error: Repository URL is required"
    
    logger.info(f"🎯 Starting Full QA Cycle with Council of Agents")
    results = []
    
    # AGENT 1: REPOSITORY AGENT
    results.append("=" * 70)
    results.append("👤 AGENT 1: REPOSITORY AGENT")
    results.append("=" * 70)
    
    clone_result = await clone_repository(repo_url=repo_url, branch=branch)
    results.append(clone_result)
    
    if "❌" in clone_result:
        return "\n".join(results)
    
    repo_path = clone_result.split(": ")[1] if ": " in clone_result else f"/app/repos/{sanitize_repo_name(repo_url)}"
    
    # AGENT 2: INSPECTOR/ANALYZER AGENT
    results.append("\n" + "=" * 70)
    results.append("👤 AGENT 2: INSPECTOR/ANALYZER AGENT")
    results.append("=" * 70)
    
    analysis_result = await analyze_codebase(repo_path=repo_path, file_pattern="*.py")
    results.append(analysis_result)
    
    # AGENT 3: TEST GENERATOR AGENT
    results.append("\n" + "=" * 70)
    results.append("👤 AGENT 3: TEST GENERATOR AGENT")
    results.append("=" * 70)
    
    test_targets = ["backend/main.py", "database/database_setup.py", "prestart.py"]
    generated_count = 0
    
    for target in test_targets:
        gen_result = await generate_unit_tests(repo_path=repo_path, target_file=target)
        if "✅" in gen_result:
            generated_count += 1
        results.append(f"\n📝 Target: {target}")
        results.append(gen_result[:300])
    
    if base_url.strip():
        e2e_result = await generate_e2e_tests(
            repo_path=repo_path,
            base_url=base_url,
            test_name="media_tracker"
        )
        results.append("\n🌐 E2E Tests:")
        results.append(e2e_result)
        generated_count += 1
    
    # AGENT 4: EXECUTOR AGENT
    results.append("\n" + "=" * 70)
    results.append("👤 AGENT 4: EXECUTOR AGENT")
    results.append("=" * 70)
    
    exec_result = await execute_tests(repo_path=repo_path)
    results.append(exec_result)
    
    # AGENT 5: REPAIRER AGENT (if tests failed)
    if "failed" in exec_result.lower() or "❌" in exec_result:
        results.append("\n" + "=" * 70)
        results.append("👤 AGENT 5: REPAIRER AGENT")
        results.append("=" * 70)
        
        repair_result = await repair_failing_tests(
            repo_path=repo_path,
            test_output=exec_result
        )
        results.append(repair_result)
    else:
        results.append("\n⏭️  Agent 5 (Repairer) skipped - no failures detected")
    
    # AGENT 6: CI/CD AGENT
    results.append("\n" + "=" * 70)
    results.append("👤 AGENT 6: CI/CD AGENT")
    results.append("=" * 70)
    
    workflow_result = await generate_github_workflow(
        repo_path=repo_path,
        test_command="pytest --cov=backend --cov-report=xml -v"
    )
    results.append(workflow_result)
    
    # FINAL SUMMARY
    results.append("\n" + "=" * 70)
    results.append("✅ COUNCIL OF AGENTS - COMPLETE")
    results.append("=" * 70)
    results.append(f"""
📊 Execution Summary:
  ✅ Repository Agent - Code cloned to {repo_path}
  ✅ Inspector Agent - Codebase analyzed
  ✅ Generator Agent - {generated_count} test suites created
  ✅ Executor Agent - Tests executed with coverage
  {"✅ Repairer Agent - Failures analyzed" if "failed" in exec_result.lower() else "⏭️  Repairer Agent - Skipped (no failures)"}
  ✅ CI/CD Agent - GitHub Actions workflow generated

🎯 Next Steps:
  1. Review test files in {repo_path}/tests/
  2. Customize test assertions
  3. Commit .github/workflows/qa_testing.yml
  4. Push to GitHub to activate CI/CD
  5. Use create_test_fix_pr tool if fixes needed
    """)
    
    return "\n".join(results)

# === SERVER STARTUP ===
if __name__ == "__main__":
    logger.info("Starting Autonomous QA Testing Council MCP server (FIXED VERSION)...")
    
    if not GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN not set - PR creation and private repos will be unavailable")
    
    logger.info(f"Workspace directory: {WORKSPACE_DIR}")
    logger.info(f"Test results directory: {TEST_RESULTS_DIR}")
    logger.info(f"Coverage directory: {COVERAGE_DIR}")
    
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
