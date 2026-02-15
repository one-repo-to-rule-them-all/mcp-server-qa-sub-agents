"""Shared utilities used by QA Council agents."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path


def sanitize_repo_name(repo_url: str) -> str:
    """Extract a safe directory name from a repository URL."""
    name = repo_url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def verify_path_exists(path: str) -> tuple[bool, str]:
    """Verify a path exists and is readable."""
    try:
        p = Path(path)
        if p.exists():
            return True, str(p)

        if os.path.exists(path):
            return True, path

        parent = p.parent
        if parent.exists():
            for child in parent.iterdir():
                if child.name == p.name:
                    return True, str(child)

        return False, f"Path not found: {path}"
    except Exception as exc:  # pragma: no cover - defensive guard
        return False, f"Path verification error: {exc}"


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
