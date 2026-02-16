"""Unit tests for qa_agents.utils.analysis_utils – AST-based code analysis."""

from __future__ import annotations

import pytest

from qa_agents.utils.analysis_utils import analyze_python_file


@pytest.mark.unit
class TestAnalyzePythonFile:
    """Verify AST extraction covers functions, classes, imports, and edge cases."""

    def test_extracts_functions(self, sample_python_file):
        result = analyze_python_file(str(sample_python_file))

        names = [f["name"] for f in result["functions"]]
        assert "public_function" in names
        assert "_private_helper" in names

    def test_async_functions_not_extracted_by_sync_walker(self, sample_python_file):
        """ast.FunctionDef does not match AsyncFunctionDef – document this gap."""
        result = analyze_python_file(str(sample_python_file))

        names = [f["name"] for f in result["functions"]]
        # async_handler uses `async def` → ast.AsyncFunctionDef, not captured
        assert "async_handler" not in names

    def test_extracts_function_args(self, sample_python_file):
        result = analyze_python_file(str(sample_python_file))

        func = next(f for f in result["functions"] if f["name"] == "public_function")
        assert "name" in func["args"]
        assert "count" in func["args"]

    def test_extracts_classes(self, sample_python_file):
        result = analyze_python_file(str(sample_python_file))

        assert len(result["classes"]) == 1
        cls = result["classes"][0]
        assert cls["name"] == "MyService"
        assert "run" in cls["methods"]
        assert "__init__" in cls["methods"]
        assert "_internal" in cls["methods"]

    def test_extracts_imports(self, sample_python_file):
        result = analyze_python_file(str(sample_python_file))

        assert "os" in result["imports"]
        assert "pathlib" in result["imports"]

    def test_counts_total_lines(self, sample_python_file):
        result = analyze_python_file(str(sample_python_file))

        assert result["total_lines"] > 0
        actual_lines = sample_python_file.read_text().splitlines()
        assert result["total_lines"] == len(actual_lines)

    def test_returns_error_for_nonexistent_file(self, tmp_path):
        result = analyze_python_file(str(tmp_path / "does_not_exist.py"))

        assert "error" in result

    def test_returns_error_for_syntax_error(self, tmp_path):
        bad_file = tmp_path / "bad_syntax.py"
        bad_file.write_text("def broken(\n", encoding="utf-8")

        result = analyze_python_file(str(bad_file))

        assert "error" in result

    def test_handles_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("", encoding="utf-8")

        result = analyze_python_file(str(empty_file))

        assert result["functions"] == []
        assert result["classes"] == []
        assert result["imports"] == []
        assert result["total_lines"] == 0
