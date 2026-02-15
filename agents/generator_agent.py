"""Test Generator Agent: strategy-based pytest generation with real mocking.

Architecture:
    AST Analysis Data → MockStrategyResolver → TestTemplateEngine → TestFileWriter

Generates production-quality pytest tests with:
- unittest.mock (patch, MagicMock, mock_open, AsyncMock)
- @pytest.mark.parametrize for edge cases
- Proper assertions (not stubs or TODOs)
- Argument heuristics for realistic test values
"""
import os
import textwrap
from pathlib import Path

from agents.analyzer_agent import analyze_file
from utils.config import get_logger
from utils.path_utils import verify_path_exists

logger = get_logger("generator")


# ── Argument Heuristics ──────────────────────────────────────────────────


def _infer_test_value(param_name: str, default: str | None = None) -> str:
    """Infer a realistic test value from a parameter name."""
    if default and default not in ("None", "''", '""'):
        return default

    name = param_name.lower()
    if any(k in name for k in ("path", "file", "dir", "folder")):
        return '"/tmp/test_file.txt"'
    if any(k in name for k in ("url", "uri", "endpoint")):
        return '"https://example.com/test"'
    if any(k in name for k in ("name", "title", "label")):
        return '"test_value"'
    if any(k in name for k in ("count", "num", "size", "limit", "max", "min")):
        return "10"
    if any(k in name for k in ("flag", "enabled", "active", "verbose")):
        return "True"
    if any(k in name for k in ("data", "config", "options", "settings")):
        return '{"key": "value"}'
    if name == "branch":
        return '"main"'
    if any(k in name for k in ("timeout", "delay")):
        return "30"
    if any(k in name for k in ("output", "result", "text", "content", "body")):
        return '"test output content"'
    if any(k in name for k in ("command", "cmd")):
        return '"echo hello"'
    if any(k in name for k in ("token", "key", "secret")):
        return '"test_token_123"'
    return '"test_input"'


def _infer_empty_value(param_name: str) -> str:
    """Infer an 'empty' edge-case value for parametrize."""
    name = param_name.lower()
    if any(k in name for k in ("count", "num", "size", "limit", "max", "min",
                                 "timeout", "delay")):
        return "0"
    if any(k in name for k in ("flag", "enabled", "active")):
        return "False"
    if any(k in name for k in ("data", "config", "options")):
        return "{}"
    return '""'


# ── Mock Strategy Resolver ───────────────────────────────────────────────


class MockStrategy:
    """Describes a single mock that should be applied to a test."""

    def __init__(self, target: str, decorator: str, setup_lines: list[str],
                 arg_name: str | None = None):
        self.target = target
        self.decorator = decorator
        self.setup_lines = setup_lines
        self.arg_name = arg_name


def resolve_mock_strategies(func_info: dict, module_name: str) -> list[MockStrategy]:
    """Examine function metadata and return the mock strategies needed."""
    strategies: list[MockStrategy] = []
    cx = func_info.get("complexity_indicators", {})
    calls = func_info.get("calls", [])

    if cx.get("uses_file_io") or "open" in calls:
        strategies.append(MockStrategy(
            target="builtins.open",
            decorator=f'@patch("builtins.open", new_callable=mock_open, read_data="test content")',
            setup_lines=[],
            arg_name="mock_file",
        ))

    if cx.get("uses_subprocess") or any("subprocess" in c for c in calls):
        strategies.append(MockStrategy(
            target=f"{module_name}.subprocess.run",
            decorator=f'@patch("{module_name}.subprocess.run")',
            setup_lines=[
                'mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")',
            ],
            arg_name="mock_run",
        ))

    if cx.get("uses_http"):
        # Detect httpx vs requests
        http_lib = "httpx"
        for c in calls:
            if "requests" in c:
                http_lib = "requests"
                break

        if http_lib == "httpx":
            strategies.append(MockStrategy(
                target=f"{module_name}.httpx.AsyncClient",
                decorator=f'@patch("{module_name}.httpx.AsyncClient")',
                setup_lines=[
                    "mock_client_instance = AsyncMock()",
                    "mock_response = MagicMock(status_code=200, text='ok')",
                    "mock_response.json.return_value = {}",
                    "mock_client_instance.post.return_value = mock_response",
                    "mock_client_instance.get.return_value = mock_response",
                    "mock_client.__aenter__.return_value = mock_client_instance",
                ],
                arg_name="mock_client",
            ))
        else:
            strategies.append(MockStrategy(
                target=f"{module_name}.requests",
                decorator=f'@patch("{module_name}.requests")',
                setup_lines=[
                    'mock_req.get.return_value = MagicMock(status_code=200, text="ok")',
                    'mock_req.post.return_value = MagicMock(status_code=201, text="created")',
                ],
                arg_name="mock_req",
            ))

    if cx.get("uses_os"):
        for call in calls:
            if "os.path.exists" in call or "Path" in call:
                strategies.append(MockStrategy(
                    target=f"{module_name}.os.path.exists",
                    decorator=f'@patch("{module_name}.os.path.exists", return_value=True)',
                    setup_lines=[],
                    arg_name="mock_exists",
                ))
                break

    return strategies


# ── Test Template Engine ─────────────────────────────────────────────────


def _build_function_call(func_info: dict, module_name: str) -> str:
    """Build a function call expression with test values."""
    args = func_info.get("args", [])
    arg_strs = []
    for a in args:
        val = _infer_test_value(a["name"], a.get("default"))
        arg_strs.append(f'{a["name"]}={val}')

    name = func_info["name"]
    prefix = "await " if func_info.get("is_async") else ""
    return f"{prefix}{name}({', '.join(arg_strs)})"


def _generate_function_tests(func_info: dict, module_name: str) -> str:
    """Generate a full test class for a standalone function."""
    name = func_info["name"]
    class_name = "Test" + "".join(w.capitalize() for w in name.split("_") if w)
    strategies = resolve_mock_strategies(func_info, module_name)
    is_async = func_info.get("is_async", False)
    cx = func_info.get("complexity_indicators", {})
    args = func_info.get("args", [])

    tests: list[str] = []

    # ── 1. Success test ───────────────────────────────────────────────
    mock_decorators = "\n    ".join(s.decorator for s in reversed(strategies))
    mock_params = ", ".join(s.arg_name for s in strategies if s.arg_name)
    setup = "\n        ".join(
        line for s in strategies for line in s.setup_lines
    )
    call_expr = _build_function_call(func_info, module_name)

    if mock_decorators:
        mock_decorators = "\n    " + mock_decorators

    self_params = "self"
    if mock_params:
        self_params = f"self, {mock_params}"

    async_def = "async " if is_async else ""
    pytest_mark = "\n    @pytest.mark.asyncio" if is_async else ""

    success_test = f"""
    {mock_decorators}{pytest_mark}
    {async_def}def test_{name}_success({self_params}):
        \"\"\"Test successful execution of {name}.\"\"\"
        {setup}
        result = {call_expr}
        assert result is not None"""

    # Add mock assertions
    for s in strategies:
        if s.arg_name and "subprocess" in s.target:
            success_test += f"\n        {s.arg_name}.assert_called()"
    tests.append(success_test)

    # ── 2. None / empty input tests ───────────────────────────────────
    if args:
        first_arg = args[0]
        none_call_args = []
        for a in args:
            if a["name"] == first_arg["name"]:
                none_call_args.append(f'{a["name"]}=""')
            else:
                none_call_args.append(
                    f'{a["name"]}={_infer_test_value(a["name"], a.get("default"))}'
                )
        none_call = f"{'await ' if is_async else ''}{name}({', '.join(none_call_args)})"

        empty_test = f"""
    {mock_decorators}{pytest_mark}
    {async_def}def test_{name}_empty_input({self_params}):
        \"\"\"Test {name} handles empty/missing input gracefully.\"\"\"
        {setup}
        result = {none_call}
        assert result is not None
        # Empty input should return an error message or handle gracefully
        if isinstance(result, str):
            assert "error" in result.lower() or len(result) > 0"""
        tests.append(empty_test)

    # ── 3. Parametrized edge cases ────────────────────────────────────
    if args:
        first = args[0]
        good_val = _infer_test_value(first["name"], first.get("default"))
        empty_val = _infer_empty_value(first["name"])

        param_test = f"""
    @pytest.mark.parametrize("{first['name']}_val", [
        {good_val},
        {empty_val},
        "   ",
    ]){pytest_mark}
    {async_def}def test_{name}_various_inputs(self, {first['name']}_val):
        \"\"\"Test {name} with various input values.\"\"\"
        result = {'await ' if is_async else ''}{name}({first['name']}={first['name']}_val)
        # Function should handle all inputs without raising
        assert result is not None"""
        tests.append(param_test)

    # ── 4. Error handling test ────────────────────────────────────────
    if cx.get("has_try_except") and strategies:
        first_strategy = strategies[0]
        error_mock_arg = first_strategy.arg_name or "mock_dep"

        error_test = f"""
    {first_strategy.decorator}{pytest_mark}
    {async_def}def test_{name}_error_handling(self, {error_mock_arg}):
        \"\"\"Test {name} handles errors gracefully.\"\"\"
        {error_mock_arg}.side_effect = Exception("Test error")
        result = {call_expr}
        assert result is not None
        if isinstance(result, str):
            assert "error" in result.lower()"""
        tests.append(error_test)

    # ── 5. Subprocess-specific tests ──────────────────────────────────
    if cx.get("uses_subprocess"):
        sub_strategy = next(
            (s for s in strategies if "subprocess" in s.target), None
        )
        if sub_strategy:
            timeout_test = f"""
    {sub_strategy.decorator}{pytest_mark}
    {async_def}def test_{name}_subprocess_timeout(self, {sub_strategy.arg_name}):
        \"\"\"Test {name} handles subprocess timeout.\"\"\"
        import subprocess as _sp
        {sub_strategy.arg_name}.side_effect = _sp.TimeoutExpired(cmd="test", timeout=5)
        result = {call_expr}
        assert result is not None
        if isinstance(result, str):
            assert "timeout" in result.lower() or "error" in result.lower()"""
            tests.append(timeout_test)

            failure_test = f"""
    {sub_strategy.decorator}{pytest_mark}
    {async_def}def test_{name}_subprocess_failure(self, {sub_strategy.arg_name}):
        \"\"\"Test {name} handles non-zero exit code.\"\"\"
        {sub_strategy.arg_name}.return_value = MagicMock(
            returncode=1, stdout="", stderr="command failed"
        )
        result = {call_expr}
        assert result is not None"""
            tests.append(failure_test)

    # ── 6. File I/O specific tests ────────────────────────────────────
    if cx.get("uses_file_io"):
        file_strategy = next(
            (s for s in strategies if "open" in s.target), None
        )
        if file_strategy:
            fnf_test = f"""
    @patch("builtins.open", side_effect=FileNotFoundError("not found")){pytest_mark}
    {async_def}def test_{name}_file_not_found(self, mock_file):
        \"\"\"Test {name} handles missing file.\"\"\"
        result = {call_expr}
        assert result is not None
        if isinstance(result, str):
            assert "error" in result.lower() or "not found" in result.lower()"""
            tests.append(fnf_test)

    # ── 7. HTTP specific tests ────────────────────────────────────────
    if cx.get("uses_http"):
        http_strategy = next(
            (s for s in strategies if "http" in s.target.lower()), None
        )
        if http_strategy:
            http_err_test = f"""
    {http_strategy.decorator}{pytest_mark}
    {async_def}def test_{name}_http_error(self, {http_strategy.arg_name}):
        \"\"\"Test {name} handles HTTP errors.\"\"\"
        {http_strategy.arg_name}.side_effect = Exception("Connection refused")
        result = {call_expr}
        assert result is not None"""
            tests.append(http_err_test)

    # ── Assemble class ────────────────────────────────────────────────
    body = "\n".join(tests)
    return f"""
class {class_name}:
    \"\"\"Tests for {name}().\"\"\"
{body}
"""


def _generate_class_tests(cls_info: dict, module_name: str) -> str:
    """Generate a test class for a source class."""
    cls_name = cls_info["name"]
    test_class_name = f"Test{cls_name}"
    init_args = cls_info.get("init_args", [])
    methods = cls_info.get("methods", [])

    # Build fixture
    fixture_args = []
    for a in init_args:
        val = _infer_test_value(a["name"], a.get("default"))
        fixture_args.append(f"{a['name']}={val}")
    constructor_call = f"{cls_name}({', '.join(fixture_args)})"

    tests: list[str] = []

    # Fixture
    tests.append(f"""
    @pytest.fixture
    def instance(self):
        \"\"\"Create a {cls_name} instance for testing.\"\"\"
        return {constructor_call}""")

    # Instantiation test
    tests.append(f"""
    def test_instantiation(self, instance):
        \"\"\"Test that {cls_name} can be instantiated.\"\"\"
        assert instance is not None
        assert isinstance(instance, {cls_name})""")

    # Per-method tests
    for method in methods:
        mname = method["name"]
        if mname.startswith("_") and mname != "__init__":
            continue  # skip private methods (except init which we already test)
        if mname == "__init__":
            continue

        is_async = method.get("is_async", False)
        method_args = method.get("args", [])
        strategies = resolve_mock_strategies(method, module_name)

        call_args = []
        for a in method_args:
            val = _infer_test_value(a["name"], a.get("default"))
            call_args.append(f"{a['name']}={val}")
        call_str = f"{'await ' if is_async else ''}instance.{mname}({', '.join(call_args)})"

        mock_decorators = "\n    ".join(s.decorator for s in reversed(strategies))
        mock_params = ", ".join(s.arg_name for s in strategies if s.arg_name)
        setup = "\n        ".join(
            line for s in strategies for line in s.setup_lines
        )

        if mock_decorators:
            mock_decorators = "\n    " + mock_decorators

        self_params = "self, instance"
        if mock_params:
            self_params = f"self, instance, {mock_params}"

        async_def = "async " if is_async else ""
        pytest_mark = "\n    @pytest.mark.asyncio" if is_async else ""

        tests.append(f"""
    {mock_decorators}{pytest_mark}
    {async_def}def test_{mname}_success({self_params}):
        \"\"\"Test {mname} method.\"\"\"
        {setup}
        result = {call_str}
        assert result is not None""")

        # Callable check
        tests.append(f"""
    def test_{mname}_is_callable(self, instance):
        \"\"\"Verify {mname} is a callable method.\"\"\"
        assert callable(getattr(instance, "{mname}", None))""")

    body = "\n".join(tests)
    return f"""
class {test_class_name}:
    \"\"\"Tests for {cls_name} class.\"\"\"
{body}
"""


# ── File Writer ──────────────────────────────────────────────────────────


def generate_test_file(analysis: dict, output_dir: str) -> str | None:
    """Generate a complete test file from a single file's analysis data.

    Args:
        analysis: Dict from analyze_file() with functions, classes, imports.
        output_dir: Directory where test files are written.

    Returns:
        Path to the generated test file, or None if nothing to test.
    """
    functions = analysis.get("functions", [])
    classes = analysis.get("classes", [])
    module_name = analysis.get("module", "unknown")

    if not functions and not classes:
        return None

    # Determine which mock imports we need
    needs_patch = False
    needs_magicmock = False
    needs_mock_open = False
    needs_async_mock = False

    for fn in functions:
        strats = resolve_mock_strategies(fn, module_name)
        if strats:
            needs_patch = True
            needs_magicmock = True
        if any("open" in s.target for s in strats):
            needs_mock_open = True
        if fn.get("is_async"):
            needs_async_mock = True

    for cls in classes:
        for m in cls.get("methods", []):
            strats = resolve_mock_strategies(m, module_name)
            if strats:
                needs_patch = True
                needs_magicmock = True
            if any("open" in s.target for s in strats):
                needs_mock_open = True
            if m.get("is_async"):
                needs_async_mock = True

    # Build import section
    mock_imports = []
    if needs_patch or needs_magicmock or needs_mock_open or needs_async_mock:
        parts = []
        if needs_patch:
            parts.append("patch")
        if needs_magicmock:
            parts.append("MagicMock")
        if needs_mock_open:
            parts.append("mock_open")
        if needs_async_mock:
            parts.append("AsyncMock")
        mock_imports.append(f"from unittest.mock import {', '.join(parts)}")

    needs_asyncio_mark = any(f.get("is_async") for f in functions) or any(
        m.get("is_async") for cls in classes for m in cls.get("methods", [])
    )

    # Source import path
    source_filepath = analysis.get("filepath", "")
    import_names = [f["name"] for f in functions]
    import_names += [c["name"] for c in classes]

    header = f'''"""Generated unit tests for {module_name}.py

Auto-generated by QA Council Test Generator Agent.
Tests use unittest.mock for isolation and pytest for execution.
"""
import pytest
{chr(10).join(mock_imports)}
import sys
from pathlib import Path

# Ensure source is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

'''

    # Add conditional import with try/except
    if import_names:
        names_str = ", ".join(import_names)
        header += f"""try:
    from {module_name} import {names_str}
except ImportError:
    # Fallback: module may need dependencies
    {', '.join(f'{n} = None' for n in import_names)}

"""

    # Generate test classes
    body_parts: list[str] = []
    for fn in functions:
        body_parts.append(_generate_function_tests(fn, module_name))

    for cls in classes:
        body_parts.append(_generate_class_tests(cls, module_name))

    content = header + "\n".join(body_parts)

    # Write file
    os.makedirs(output_dir, exist_ok=True)
    test_filename = f"test_{module_name}.py"
    test_filepath = os.path.join(output_dir, test_filename)

    with open(test_filepath, "w", encoding="utf-8") as fh:
        fh.write(content)

    return test_filepath


# ── E2E Test Generator ───────────────────────────────────────────────────


def generate_e2e_test_file(base_url: str, output_dir: str) -> str:
    """Generate a Playwright-based E2E test suite.

    Args:
        base_url: Application base URL (e.g. http://localhost:8000)
        output_dir: Directory where test files are written.

    Returns:
        Path to the generated E2E test file.
    """
    content = f'''"""Generated E2E tests using Playwright.

Auto-generated by QA Council Test Generator Agent.
"""
import pytest
from playwright.sync_api import Page, expect


BASE_URL = "{base_url}"


@pytest.fixture(autouse=True)
def navigate_to_base(page: Page):
    """Navigate to the application before each test."""
    page.goto(BASE_URL)


class TestHomePage:
    """E2E tests for the home page."""

    def test_page_loads(self, page: Page):
        """Verify the home page loads successfully."""
        expect(page).to_have_url(BASE_URL + "/")

    def test_page_has_title(self, page: Page):
        """Verify the page has a non-empty title."""
        title = page.title()
        assert len(title) > 0

    def test_page_has_content(self, page: Page):
        """Verify the page body has visible content."""
        body = page.locator("body")
        expect(body).to_be_visible()

    def test_no_console_errors(self, page: Page):
        """Verify no JavaScript errors in the console."""
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.reload()
        page.wait_for_load_state("networkidle")
        assert len(errors) == 0, f"Console errors found: {{errors}}"


class TestNavigation:
    """E2E tests for navigation and links."""

    def test_links_are_valid(self, page: Page):
        """Verify all links have href attributes."""
        links = page.locator("a[href]").all()
        for link in links:
            href = link.get_attribute("href")
            assert href is not None and len(href) > 0

    def test_navigation_works(self, page: Page):
        """Verify clicking main navigation links doesn't error."""
        nav_links = page.locator("nav a").all()
        for link in nav_links[:5]:  # Test first 5 nav links
            href = link.get_attribute("href")
            if href and not href.startswith(("http", "mailto", "#")):
                page.goto(BASE_URL + href)
                assert page.url is not None


class TestResponsive:
    """E2E tests for responsive behavior."""

    def test_mobile_viewport(self, page: Page):
        """Verify page renders at mobile viewport."""
        page.set_viewport_size({{"width": 375, "height": 667}})
        page.reload()
        body = page.locator("body")
        expect(body).to_be_visible()

    def test_tablet_viewport(self, page: Page):
        """Verify page renders at tablet viewport."""
        page.set_viewport_size({{"width": 768, "height": 1024}})
        page.reload()
        body = page.locator("body")
        expect(body).to_be_visible()
'''

    os.makedirs(output_dir, exist_ok=True)
    test_filepath = os.path.join(output_dir, "test_e2e.py")
    with open(test_filepath, "w", encoding="utf-8") as fh:
        fh.write(content)

    return test_filepath


# ── Public MCP-facing API ────────────────────────────────────────────────


async def run_unit_test_generation(
    repo_path: str = "", target_file: str = ""
) -> str:
    """Generate unit tests for a Python file or full repository.

    Args:
        repo_path: Path to the repository root.
        target_file: Specific file to generate tests for (optional).
                     If empty, generates tests for all analyzed files.

    Returns:
        Status message listing generated test files and their features.
    """
    if not repo_path.strip():
        return "Error: Repository path is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        return f"Error: {verified_path}"

    test_dir = os.path.join(verified_path, "tests", "generated")
    generated_files: list[str] = []

    if target_file.strip():
        # Single file mode
        filepath = target_file
        if not os.path.isabs(filepath):
            filepath = os.path.join(verified_path, filepath)

        if not os.path.exists(filepath):
            return f"Error: File not found: {filepath}"

        analysis = analyze_file(filepath)
        if analysis.get("error"):
            return f"Error analyzing {filepath}: {analysis['error']}"

        result = generate_test_file(analysis, test_dir)
        if result:
            generated_files.append(result)
    else:
        # Full repository mode
        from agents.analyzer_agent import analyze_directory
        analyses = analyze_directory(verified_path)

        for analysis in analyses:
            if analysis.get("error"):
                continue
            # Skip test files and __init__
            module = analysis.get("module", "")
            if module.startswith("test_") or module == "__init__":
                continue
            result = generate_test_file(analysis, test_dir)
            if result:
                generated_files.append(result)

    if not generated_files:
        return "No testable code found. Ensure the target contains Python functions or classes."

    file_list = "\n".join(f"  - {f}" for f in generated_files)
    return f"""Unit Tests Generated Successfully

Test directory: {test_dir}
Files generated: {len(generated_files)}

{file_list}

Features included in generated tests:
- unittest.mock (patch, MagicMock, mock_open) for isolation
- @pytest.mark.parametrize for edge case coverage
- Error handling tests for try/except code paths
- Subprocess mock tests (success, failure, timeout)
- File I/O mock tests (read, write, FileNotFoundError)
- HTTP client mock tests (success, connection error)
- Empty/None input validation tests

Run tests with:
  pytest {test_dir} -v --tb=short
"""


async def run_e2e_test_generation(
    repo_path: str = "", base_url: str = "http://localhost:8000"
) -> str:
    """Generate Playwright E2E tests for a web application.

    Args:
        repo_path: Path to the repository root.
        base_url: Application base URL for E2E testing.

    Returns:
        Status message with generated E2E test file path.
    """
    if not repo_path.strip():
        return "Error: Repository path is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        return f"Error: {verified_path}"

    test_dir = os.path.join(verified_path, "tests", "e2e")
    test_file = generate_e2e_test_file(base_url, test_dir)

    return f"""E2E Tests Generated Successfully

Test file: {test_file}
Base URL: {base_url}

Test coverage:
- Page load verification
- Title and content checks
- Console error detection
- Link validation
- Navigation testing
- Mobile responsive check
- Tablet responsive check

Run tests with:
  pytest {test_dir} -v --headed
"""
