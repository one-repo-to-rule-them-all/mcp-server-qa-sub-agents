# Autonomous QA Testing Council MCP Server

A Model Context Protocol (MCP) server that provides a multi-agent autonomous testing system for Python applications. Inspired by best practices from OpenObserve's autonomous QA testing architecture.

## Purpose

This MCP server orchestrates a "Council of Sub-Agents" that automates the entire software testing lifecycle including code analysis, test generation, execution, and repair for Python applications with both frontend (Playwright) and backend (pytest) testing capabilities.

## Features

### Current Implementation

- **`clone_repository`** - Clone or update GitHub repositories for testing
- **`analyze_codebase`** - Analyze Python codebase structure and identify testable components (functions, classes, imports)
- **`generate_unit_tests`** - Generate pytest unit tests for Python functions and classes
- **`generate_e2e_tests`** - Generate Playwright E2E tests for web applications
- **`execute_tests`** - Run pytest with coverage reporting and HTML reports
- **`repair_failing_tests`** - Analyze test failures and provide intelligent repair suggestions
- **`generate_github_workflow`** - Create GitHub Actions CI/CD workflows for automated testing
- **`orchestrate_full_qa_cycle`** - Complete end-to-end QA automation (clone → analyze → generate → test → report)

### Agent Architecture

The system implements a council of specialized agents:

1. **Repository Agent** - Handles git operations and code retrieval
2. **Analyzer Agent** - Performs AST-based code analysis to identify testable components
3. **Test Generator Agent** - Creates unit and E2E tests based on code structure
4. **Executor Agent** - Runs tests with pytest/Playwright and collects metrics
5. **Repair Agent** - Analyzes failures and suggests fixes
6. **CI/CD Agent** - Generates deployment pipelines
7. **Orchestrator Agent** - Coordinates all agents for full automation

## Prerequisites

- Docker Desktop with MCP Toolkit enabled
- Docker MCP CLI plugin (`docker mcp` command)
- GitHub account (optional: GitHub Personal Access Token for private repos)

## Installation

See the step-by-step instructions provided with the files.

## Usage Examples

In Claude Desktop, you can ask:

### Basic Operations
- "Clone the repository https://github.com/user/repo and analyze its test coverage"
- "Analyze the Python codebase at /app/repos/myproject"
- "Generate unit tests for the file src/utils/helpers.py"
- "Create E2E tests for https://myapp.example.com"

### Test Execution
- "Run all tests in the repository and show me the coverage report"
- "Execute tests for the authentication module"
- "What tests are failing and how can I fix them?"

### Full Automation
- "Run a complete QA cycle on https://github.com/user/webapp"
- "Set up automated testing for my repository with GitHub Actions"
- "Analyze, test, and generate a CI/CD pipeline for my project"

## Architecture
```
Claude Desktop → MCP Gateway → QA Council MCP Server → GitHub/File System
                                         ↓
                        [Council of Sub-Agents]
                                         ↓
                    pytest + Playwright + Coverage
                                         ↓
                         Test Reports & Metrics
```

## Development

### Local Testing
```bash
# Set environment variables for testing
export GITHUB_TOKEN="ghp_your_token_here"

# Run directly
python qa_council_server.py

# Test MCP protocol
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python qa_council_server.py
```

### Adding New Tools

1. Add the function to `qa_council_server.py`
2. Decorate with `@mcp.tool()`
3. Ensure single-line docstring
4. Update the catalog entry with the new tool name
5. Rebuild the Docker image

### Extending CI/CD Support

The `generate_github_workflow` function can be extended to support:
- GitLab CI (.gitlab-ci.yml)
- Jenkins (Jenkinsfile)
- CircleCI (.circleci/config.yml)
- Azure Pipelines (azure-pipelines.yml)

## Test Data Generation

The system automatically generates:
- Test fixtures based on function signatures
- Mock data for API testing
- Sample inputs for edge case testing
- Playwright page objects for E2E tests

## Coverage Metrics

All test executions include:
- Line coverage percentage
- Branch coverage analysis
- HTML coverage reports
- XML coverage for CI/CD integration
- Test execution time metrics

## Troubleshooting

### Tools Not Appearing

- Verify Docker image built successfully: `docker images | grep qa-council`
- Check catalog and registry files
- Ensure Claude Desktop config includes custom catalog
- Restart Claude Desktop completely

### Repository Clone Failures

- Verify GitHub token is set correctly
- Check repository URL format
- Ensure network connectivity
- For private repos, token must have repo access

### Test Execution Errors

- Verify pytest and playwright are installed
- Check Python version compatibility (3.11+)
- Ensure test files follow pytest conventions
- Review test output for specific error messages

### Playwright Issues

- Browser installation: `playwright install chromium`
- For headless errors, ensure dependencies: `playwright install-deps`
- Check display settings for headed mode

## Security Considerations

- GitHub tokens stored in Docker Desktop secrets
- All operations run as non-root user (mcpuser)
- Repository clones isolated in container
- No credential logging or exposure
- Test results contain no sensitive data

## Performance Optimization

- Repository cloning uses shallow clones for speed
- Test execution parallelized when possible
- Coverage collection optimized for large codebases
- Results cached for repeated executions

## Future Enhancements

- Integration with test data generation libraries (Faker, Factory Boy)
- AI-powered test improvement suggestions
- Automated test data cleanup
- Integration testing with Docker Compose
- Performance testing with Locust
- Visual regression testing
- Mutation testing support

## License

MIT License