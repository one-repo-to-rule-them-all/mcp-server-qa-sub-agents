"""Analyzer agent for codebase structure discovery."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .utils import analyze_python_file, verify_path_exists

logger = logging.getLogger("qa-council-server.analyzer-agent")

EXCLUDED_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}

FRONTEND_ENTRYPOINT_CANDIDATES = [
    "frontend/src/App.tsx",
    "frontend/src/App.jsx",
    "frontend/src/App.ts",
    "frontend/src/App.js",
    "frontend/src/app.tsx",
    "frontend/src/app.jsx",
    "frontend/src/app.ts",
    "frontend/src/app.js",
]


@dataclass
class AnalysisResult:
    """Structured analysis output consumable by downstream agents."""

    python_targets: list[str] = field(default_factory=list)
    frontend_targets: list[str] = field(default_factory=list)
    file_details: list[dict] = field(default_factory=list)
    total_functions: int = 0
    total_classes: int = 0
    error: str = ""

    @property
    def all_targets(self) -> list[str]:
        """Combined Python and frontend targets for test generation."""
        return self.python_targets + self.frontend_targets

    def to_display_string(self) -> str:
        """Format for human-readable display output."""
        if self.error:
            return self.error

        result = f"""📊 Codebase Analysis Complete

📁 Files analyzed: {len(self.file_details)}
⚡ Functions found: {self.total_functions}
🏗️ Classes found: {self.total_classes}

Top files for testing:
"""

        for i, file_info in enumerate(self.file_details[:10], 1):
            if "error" not in file_info:
                result += f"\n{i}. {file_info['path']}"
                result += f"\n   - Functions: {len(file_info.get('functions', []))}"
                result += f"\n   - Classes: {len(file_info.get('classes', []))}"

        if self.frontend_targets:
            result += "\n\nFrontend entrypoints detected:"
            for target in self.frontend_targets:
                result += f"\n  - {target}"

        return result


def _is_test_file(path: Path) -> bool:
    """Unified test-file exclusion covering both analyzer and orchestrator rules."""
    return (
        path.name.startswith("test_")
        or path.name.endswith("_test.py")
        or "tests" in path.parts
    )


def _discover_frontend_targets(repo: Path) -> list[str]:
    """Find frontend entrypoint files suitable for test generation."""
    for candidate in FRONTEND_ENTRYPOINT_CANDIDATES:
        if (repo / candidate).exists():
            return [candidate]
    return []


async def analyze_codebase_structured(repo_path: str, file_pattern: str = "*.py") -> AnalysisResult:
    """Analyze codebase and return structured data for downstream agents."""
    logger.info("Starting codebase analysis: repo_path=%s, pattern=%s", repo_path, file_pattern)

    if not repo_path.strip():
        logger.warning("Analysis aborted: repository path was empty")
        return AnalysisResult(error="❌ Error: Repository path is required")

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        logger.warning("Analysis aborted: invalid repository path (%s)", verified_path)
        return AnalysisResult(error=f"❌ Error: Repository path issue - {verified_path}")

    repo = Path(verified_path)
    if not repo.exists() or not repo.is_dir():
        logger.warning("Analysis aborted: verified path is not a directory (%s)", verified_path)
        return AnalysisResult(error=f"❌ Error: Invalid repository path: {verified_path}")

    # --- Python targets ---
    py_files = [
        f
        for f in repo.rglob(file_pattern)
        if not EXCLUDED_DIRS.intersection(f.parts)
        and not _is_test_file(f)
        and f.name != "__init__.py"
    ]

    file_details = []
    python_targets = []
    for py_file in sorted(py_files):
        rel = str(py_file.relative_to(repo))
        python_targets.append(rel)

    # Detailed AST analysis for first 50 files (for display)
    for py_file in sorted(py_files)[:50]:
        rel = str(py_file.relative_to(repo))
        file_analysis = analyze_python_file(str(py_file))
        file_analysis["path"] = rel
        file_details.append(file_analysis)

    total_functions = sum(len(f.get("functions", [])) for f in file_details)
    total_classes = sum(len(f.get("classes", [])) for f in file_details)

    # --- Frontend targets ---
    frontend_targets = _discover_frontend_targets(repo)

    logger.info(
        "Analysis complete: files=%d, functions=%d, classes=%d, frontend=%d",
        len(python_targets),
        total_functions,
        total_classes,
        len(frontend_targets),
    )

    return AnalysisResult(
        python_targets=python_targets,
        frontend_targets=frontend_targets,
        file_details=file_details,
        total_functions=total_functions,
        total_classes=total_classes,
    )


async def analyze_codebase(repo_path: str, file_pattern: str = "*.py") -> str:
    """Analyze Python codebase structure and identify testable components."""
    result = await analyze_codebase_structured(repo_path, file_pattern)
    return result.to_display_string() if not result.error else result.error
