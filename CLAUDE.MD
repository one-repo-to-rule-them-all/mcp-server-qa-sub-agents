# Autonomous QA Testing Council - Implementation Guide

## Overview

This MCP server implements a multi-agent autonomous testing system for Python applications. It follows the "Council of Sub-Agents" pattern where specialized agents collaborate to handle different aspects of the QA lifecycle.

## Agent Responsibilities

### 1. Repository Agent
- **Purpose**: Source code management
- **Implementation**: `clone_repository()` tool
- **Functions**: Clone/update repos, branch management, Git operations

### 2. Analyzer Agent
- **Purpose**: Code comprehension and analysis
- **Implementation**: `analyze_codebase()` tool using Python AST
- **Functions**: Extract functions, classes, imports, identify testable components

### 3. Test Generator Agent
- **Purpose**: Create test code
- **Implementation**: `generate_unit_tests()`, `generate_e2e_tests()`
- **Functions**: Template-based test generation, fixture creation

### 4. Executor Agent
- **Purpose**: Run tests and collect metrics
- **Implementation**: `execute_tests()` tool
- **Functions**: pytest/Playwright execution, coverage collection, report generation

### 5. Repair Agent
- **Purpose**: Diagnose and fix test failures
- **Implementation**: `repair_failing_tests()` tool
- **Functions**: Parse errors, suggest fixes, pattern matching for common issues

### 6. CI/CD Agent
- **Purpose**: Pipeline automation
- **Implementation**: `generate_github_workflow()` tool
- **Functions**: Generate workflow YAML, configure triggers, set up jobs

### 7. Orchestrator Agent
- **Purpose**: Coordinate full lifecycle
- **Implementation**: `orchestrate_full_qa_cycle()` tool
- **Functions**: Execute agents in sequence, handle failures, aggregate results

## Technical Architecture

### Code Analysis (AST-based)
```python
# Uses Python's ast module to parse source code
# Extracts: functions, classes, methods, imports
# Identifies: async functions, decorators, arguments
```

### Test Generation Patterns
```python
# Unit Tests: pytest-based with class/function fixtures
# E2E Tests: Playwright with page fixtures
# Integration Tests: Combines unit test patterns
```

### Test Execution Pipeline
```
Source Code → AST Analysis → Test Generation → Execution → Coverage → Reporting
```

## Best Practices Implemented

### From OpenObserve AI Agent Architecture:
1. **Modular Agent Design** - Each agent has single responsibility
2. **Error Recovery** - Agents handle failures gracefully
3. **Metrics Collection** - Coverage, timing, success rates
4. **CI/CD Integration** - Automated pipeline generation

### Software Engineering Practices:
1. **Separation of Concerns** - Clear agent boundaries
2. **DRY Principle** - Reusable utility functions
3. **Fail Fast** - Early validation of inputs
4. **Logging** - Comprehensive stderr logging
5. **Type Safety** - Consistent string-based parameters

## Usage Patterns

### Simple: Single Tool
```
User: "Generate unit tests for myfile.py"
→ generate_unit_tests() tool called
→ AST analysis → Template application → File creation
```

### Complex: Multi-Agent Orchestration
```
User: "Set up automated testing for my repo"
→ orchestrate_full_qa_cycle() called
→ Repository Agent clones code
→ Analyzer Agent examines structure
→ Generator Agent creates tests
→ Executor Agent runs tests
→ CI/CD Agent creates workflow
```

## Extensibility Points

### Adding New Test Types
1. Create generator function (e.g., `generate_integration_tests()`)
2. Add MCP tool decorator
3. Update orchestrator to include new test type

### Supporting New Languages
1. Add language-specific parser (e.g., esprima for JavaScript)
2. Create language-specific test templates
3. Update analyzer to handle new file types

### Adding New CI/CD Platforms
1. Create workflow template (e.g., GitLab CI)
2. Add generator function
3. Extend `generate_github_workflow()` pattern

## Configuration

### Environment Variables
- `GITHUB_TOKEN`: GitHub personal access token (optional)
- `WORKSPACE_DIR`: Repository clone location
- `TEST_RESULTS_DIR`: Test output location
- `COVERAGE_DIR`: Coverage report location

### Docker Volumes
- `/app/repos`: Persistent repository storage
- `/app/test_results`: Test execution results
- `/app/coverage`: Coverage reports

## Error Handling Strategy

1. **Input Validation**: Check all parameters before execution
2. **Graceful Degradation**: Return partial results on non-critical errors
3. **User-Friendly Messages**: Emoji-prefixed status messages
4. **Detailed Logging**: stderr logs for debugging
5. **Recovery Suggestions**: Repair agent provides actionable fixes

## Performance Considerations

- **Repository Cloning**: Shallow clones for speed
- **AST Parsing**: Limited to 50 files per analysis by default
- **Test Execution**: 5-minute timeout prevents hangs
- **Coverage Collection**: XML format for efficiency

## Testing the MCP Server
```bash
# Test repository cloning
echo '{"method":"tools/call","params":{"name":"clone_repository","arguments":{"repo_url":"https://github.com/test/repo"}}}' | python qa_council_server.py

# Test code analysis
echo '{"method":"tools/call","params":{"name":"analyze_codebase","arguments":{"repo_path":"/app/repos/myrepo"}}}' | python qa_council_server.py
```

## Integration with Claude

Claude can orchestrate complex QA workflows by:
1. Understanding user intent ("test my web app")
2. Selecting appropriate agent(s)
3. Chaining tools in logical sequence
4. Presenting results in user-friendly format

Example conversation:
```
User: "My tests are failing, can you help?"
Claude: → calls execute_tests() to see failures
        → calls repair_failing_tests() with output
        → presents suggestions with context
```

## Maintenance

### Updating Dependencies
- Edit `requirements.txt`
- Rebuild Docker image
- Test with `docker run` before deployment

### Adding Features
- Follow single-responsibility principle
- Add comprehensive error handling
- Update documentation
- Test in isolation first

### Monitoring
- Check Docker logs: `docker logs <container>`
- Review test result files in `/app/test_results`
- Monitor coverage trends in `/app/coverage`

## References

- [Autonomous QA Testing with AI Agents](https://openobserve.ai/blog/autonomous-qa-testing-ai-agents-claude-code/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [pytest Documentation](https://docs.pytest.org/)
- [Playwright Python Documentation](https://playwright.dev/python/)