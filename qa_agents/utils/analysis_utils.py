"""Code analysis helpers shared by analyzer and generator agents."""

from __future__ import annotations

import ast
from pathlib import Path


def analyze_python_file(file_path: str) -> dict:
    """Analyze Python file structure and extract testable components."""
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        tree = ast.parse(content)

        functions: list[dict] = []
        classes: list[dict] = []
        imports: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(
                    {
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "lineno": node.lineno,
                    }
                )
            elif isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                classes.append({"name": node.name, "methods": methods, "lineno": node.lineno})
            elif isinstance(node, ast.Import):
                imports.extend([alias.name for alias in node.names])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        return {
            "functions": functions,
            "classes": classes,
            "imports": imports,
            "total_lines": len(content.splitlines()),
        }
    except Exception as exc:
        return {"error": str(exc)}
