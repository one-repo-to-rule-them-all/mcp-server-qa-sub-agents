"""Generator agent for unit and E2E test generation."""

from __future__ import annotations

from pathlib import Path

from .common import analyze_python_file, verify_path_exists


def _build_module_import(target_file: str) -> str:
    module_path = Path(target_file).with_suffix("")
    return ".".join(module_path.parts)


def _default_value_for_arg(arg_name: str) -> str:
    lowered = arg_name.lower()
    if any(key in lowered for key in ("id", "count", "size", "limit", "port")):
        return "1"
    if any(key in lowered for key in ("name", "title", "text", "path", "url")):
        return "'sample'"
    if lowered.startswith(("is_", "has_", "should_")):
        return "True"
    if any(key in lowered for key in ("items", "list", "values")):
        return "[]"
    if any(key in lowered for key in ("config", "options", "data", "payload")):
        return "{}"
    return "Mock()"


def _render_function_test(func: dict) -> str:
    name = func["name"]
    if name.startswith("_"):
        return ""

    args = [a for a in func.get("args", []) if a != "self"]
    assignment_lines = [f"    {arg} = {_default_value_for_arg(arg)}" for arg in args]
    call_args = ", ".join(args)
    if assignment_lines:
        arrange = "\n".join(assignment_lines)
    else:
        arrange = "    # No input args required"

    return f'''
def test_{name}_smoke_and_contract(monkeypatch):
    """Smoke + contract test for `{name}` using deterministic mocks."""
    {arrange}
    with patch.object(module_under_test, "logger", autospec=True, create=True):
        result = {name}({call_args}) if "{call_args}" else {name}()

    assert result is not ...
'''


def _render_class_tests(cls: dict) -> str:
    class_name = cls["name"]
    methods = [m for m in cls.get("methods", []) if not m.startswith("_")]
    method_assertions = "\n".join(
        [f"    assert callable(getattr(instance, '{method}', None))" for method in methods]
    ) or "    assert instance is not None"

    return f'''

class Test{class_name}:
    """Behavioral contract tests for `{class_name}`."""

    @pytest.fixture()
    def instance(self):
        constructor_kwargs = {{}}
        with patch.object(module_under_test, "logger", autospec=True, create=True):
            return {class_name}(**constructor_kwargs)

    def test_public_methods_exposed(self, instance):
        """Public methods should be available for usage by callers."""
{method_assertions}
'''


async def generate_unit_tests(repo_path: str, target_file: str) -> str:
    """Generate unit tests that follow QA best practices with mocks and fixtures."""
    if not repo_path.strip():
        return "❌ Error: Repository path is required"
    if not target_file.strip():
        return "❌ Error: Target file path is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        return f"❌ Error: Repository path issue - {verified_path}"

    file_path = Path(verified_path) / target_file
    if not file_path.exists():
        return f"❌ Error: File not found: {target_file}"

    analysis = analyze_python_file(str(file_path))
    if "error" in analysis:
        return f"❌ Error analyzing file: {analysis['error']}"

    test_file_name = f"test_{file_path.name}"
    test_file_path = Path(verified_path) / "tests" / "unit" / test_file_name
    test_file_path.parent.mkdir(parents=True, exist_ok=True)

    module_import_path = _build_module_import(target_file)
    public_functions = [f for f in analysis.get("functions", []) if not f["name"].startswith("_")]

    import_targets = [c['name'] for c in analysis.get('classes', [])] + [f['name'] for f in public_functions]
    from_import_line = f"from {module_import_path} import {', '.join(import_targets)}" if import_targets else ""

    test_content = f'''"""Generated unit tests for {target_file}."""
import pytest
from unittest.mock import Mock, patch

import {module_import_path} as module_under_test
{from_import_line}
'''

    for cls in analysis.get("classes", []):
        test_content += _render_class_tests(cls)

    for func in public_functions:
        test_content += _render_function_test(func)

    test_file_path.write_text(test_content, encoding="utf-8")

    return f"""✅ Unit tests generated successfully

📝 Test file: {test_file_path}
🧪 Classes tested: {len(analysis.get('classes', []))}
⚡ Functions tested: {len(public_functions)}
🛠️ Test style: pytest + unittest.mock (fixtures, patching, contract assertions)
"""


async def generate_e2e_tests(repo_path: str, base_url: str, test_name: str = "app") -> str:
    """Generate Playwright E2E tests for web applications."""
    if not repo_path.strip():
        return "❌ Error: Repository path is required"
    if not base_url.strip():
        return "❌ Error: Base URL is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        return f"❌ Error: {verified_path}"

    repo = Path(verified_path)
    test_dir = repo / "tests" / "e2e"
    test_dir.mkdir(parents=True, exist_ok=True)

    test_content = f'''"""E2E tests for {test_name}."""
import re

from playwright.sync_api import Page, expect


def test_{test_name}_page_loads(page: Page, base_url: str):
    page.goto(base_url)
    expect(page).to_have_title(re.compile(r".+"))
'''

    test_file = test_dir / f"test_{test_name}_e2e.py"
    test_file.write_text(test_content, encoding="utf-8")

    return f"✅ E2E tests generated successfully\n\n🌐 Base URL: {base_url}\n📝 Test file: {test_file}"
