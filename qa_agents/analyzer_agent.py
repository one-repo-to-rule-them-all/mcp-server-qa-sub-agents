"""Analyzer agent for codebase structure discovery."""

from __future__ import annotations

from pathlib import Path

from .common import analyze_python_file, verify_path_exists


async def analyze_codebase(repo_path: str, file_pattern: str = "*.py") -> str:
    """Analyze Python codebase structure and identify testable components."""
    if not repo_path.strip():
        return "❌ Error: Repository path is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        return f"❌ Error: Repository path issue - {verified_path}"

    repo = Path(verified_path)
    if not repo.exists() or not repo.is_dir():
        return f"❌ Error: Invalid repository path: {verified_path}"

    py_files = list(repo.rglob(file_pattern))
    py_files = [f for f in py_files if ".git" not in str(f) and "__pycache__" not in str(f)]

    if not py_files:
        return f"⚠️ No Python files found matching pattern: {file_pattern}"

    analysis = {"total_files": len(py_files), "files": []}
    for py_file in py_files[:50]:
        file_analysis = analyze_python_file(str(py_file))
        file_analysis["path"] = str(py_file.relative_to(repo))
        analysis["files"].append(file_analysis)

    total_functions = sum(len(f.get("functions", [])) for f in analysis["files"])
    total_classes = sum(len(f.get("classes", [])) for f in analysis["files"])

    result = f"""📊 Codebase Analysis Complete

📁 Files analyzed: {analysis['total_files']}
⚡ Functions found: {total_functions}
🏗️ Classes found: {total_classes}

Top files for testing:
"""

    for i, file_info in enumerate(analysis["files"][:10], 1):
        if "error" not in file_info:
            result += f"\n{i}. {file_info['path']}"
            result += f"\n   - Functions: {len(file_info['functions'])}"
            result += f"\n   - Classes: {len(file_info['classes'])}"

    return result
