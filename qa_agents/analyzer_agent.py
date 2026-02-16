"""Analyzer agent for codebase structure discovery."""

from __future__ import annotations

import logging
from pathlib import Path

from .utils import analyze_python_file, verify_path_exists

logger = logging.getLogger("qa-council-server.analyzer-agent")


async def analyze_codebase(repo_path: str, file_pattern: str = "*.py") -> str:
    """Analyze Python codebase structure and identify testable components."""
    logger.info("Starting codebase analysis: repo_path=%s, pattern=%s", repo_path, file_pattern)

    if not repo_path.strip():
        logger.warning("Analysis aborted: repository path was empty")
        return "❌ Error: Repository path is required"

    # Validate path before scanning the repository tree.
    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        logger.warning("Analysis aborted: invalid repository path (%s)", verified_path)
        return f"❌ Error: Repository path issue - {verified_path}"

    repo = Path(verified_path)
    if not repo.exists() or not repo.is_dir():
        logger.warning("Analysis aborted: verified path is not a directory (%s)", verified_path)
        return f"❌ Error: Invalid repository path: {verified_path}"

    py_files = list(repo.rglob(file_pattern))
    excluded_parts = {".git", "__pycache__", ".venv", "venv", "node_modules"}
    py_files = [
        f
        for f in py_files
        if not excluded_parts.intersection(f.parts)
        and not f.name.startswith("test_")
        and not f.name.endswith("_test.py")
        and "tests" not in f.parts
    ]

    if not py_files:
        logger.info("No files matched pattern during analysis: %s", file_pattern)
        return f"⚠️ No Python files found matching pattern: {file_pattern}"

    logger.info("Found %d candidate Python files for analysis", len(py_files))

    analysis = {"total_files": len(py_files), "files": []}
    for py_file in py_files[:50]:
        file_analysis = analyze_python_file(str(py_file))
        file_analysis["path"] = str(py_file.relative_to(repo))
        analysis["files"].append(file_analysis)

    total_functions = sum(len(f.get("functions", [])) for f in analysis["files"])
    total_classes = sum(len(f.get("classes", [])) for f in analysis["files"])
    logger.info(
        "Analysis complete: files=%d, functions=%d, classes=%d",
        analysis["total_files"],
        total_functions,
        total_classes,
    )

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
