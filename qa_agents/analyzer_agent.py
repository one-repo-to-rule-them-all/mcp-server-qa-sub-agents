"""Inspector/Analyst agents for codebase discovery and manifests."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .audit_schema import TechStackManifest
from .utils import analyze_python_file, verify_path_exists

logger = logging.getLogger("qa-council-server.analyzer-agent")

EXCLUDED_PARTS = {".git", "__pycache__", ".venv", "venv", "node_modules"}


def discover_unit_test_targets(repo: Path) -> list[str]:
    """Return generator targets discovered during analysis (python + frontend entrypoint)."""
    py_targets = sorted(
        str(path.relative_to(repo))
        for path in repo.rglob("*.py")
        if not EXCLUDED_PARTS.intersection(path.parts)
        and "tests" not in path.parts
        and not path.name.endswith("_test.py")
        and not path.name.startswith("test_")
        and path.name != "__init__.py"
    )

    frontend_candidates = [
        "frontend/src/App.tsx",
        "frontend/src/App.jsx",
        "frontend/src/App.ts",
        "frontend/src/App.js",
        "frontend/src/app.tsx",
        "frontend/src/app.jsx",
        "frontend/src/app.ts",
        "frontend/src/app.js",
    ]
    for candidate in frontend_candidates:
        if (repo / candidate).exists():
            py_targets.append(candidate)
            break

    return py_targets


def discover_tech_stack_manifest(repo: Path) -> TechStackManifest:
    """Infer a TechStackManifest from common repository markers."""
    backend_lang = "unknown"
    if any(repo.rglob("*.py")):
        backend_lang = "python/pytest"
    elif any(repo.rglob("*.java")):
        backend_lang = "java/junit"

    frontend_framework = "none"
    if (repo / "package.json").exists():
        package_text = (repo / "package.json").read_text(encoding="utf-8", errors="ignore").lower()
        if "react" in package_text:
            frontend_framework = "react"
        elif "vue" in package_text:
            frontend_framework = "vue"
        else:
            frontend_framework = "javascript"

    db_type = "unknown"
    for marker, value in (("postgres", "postgres"), ("mysql", "mysql"), ("sqlite", "sqlite"), ("mongodb", "mongodb")):
        if any(marker in path.name.lower() for path in repo.rglob("*")):
            db_type = value
            break

    auth_mechanism = "unknown"
    for marker, value in (("jwt", "jwt"), ("oauth", "oauth"), ("session", "session-cookie"), ("auth", "token-based")):
        if any(marker in str(path).lower() for path in repo.rglob("*.py")):
            auth_mechanism = value
            break

    harness = "pytest"
    if backend_lang.startswith("java"):
        harness = "junit + playwright-java"
    elif frontend_framework == "react":
        harness = "pytest + pytest-playwright + rtl/vitest"

    return TechStackManifest(
        backend_lang=backend_lang,
        frontend_framework=frontend_framework,
        db_type=db_type,
        auth_mechanism=auth_mechanism,
        recommended_test_harness=harness,
    )


def discover_testable_surfaces(repo: Path) -> dict:
    """Discover high-value testable surfaces via lightweight AST inspection."""
    api_endpoints: list[str] = []
    ui_components: list[str] = []
    logic_flows: list[str] = []

    for py_file in repo.rglob("*.py"):
        if EXCLUDED_PARTS.intersection(py_file.parts) or "tests" in py_file.parts:
            continue
        analysis = analyze_python_file(str(py_file))
        if "error" in analysis:
            continue
        relative = str(py_file.relative_to(repo))
        api_endpoints.extend([f"{relative}:{func['name']}" for func in analysis.get("functions", []) if func["name"].startswith(("get_", "post_", "put_", "delete_"))])
        logic_flows.extend([f"{relative}:{func['name']}" for func in analysis.get("functions", []) if not func["name"].startswith("_")])

    for component in repo.rglob("*.tsx"):
        if EXCLUDED_PARTS.intersection(component.parts):
            continue
        ui_components.append(str(component.relative_to(repo)))

    return {
        "api_endpoints": sorted(set(api_endpoints))[:100],
        "ui_components": sorted(set(ui_components))[:100],
        "logic_flows": sorted(set(logic_flows))[:200],
    }


async def analyze_codebase(repo_path: str, file_pattern: str = "*.py") -> str:
    """Analyze Python codebase structure and identify testable components."""
    logger.info("Starting codebase analysis: repo_path=%s, pattern=%s", repo_path, file_pattern)

    if not repo_path.strip():
        logger.warning("Analysis aborted: repository path was empty")
        return "❌ Error: Repository path is required"

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        logger.warning("Analysis aborted: invalid repository path (%s)", verified_path)
        return f"❌ Error: Repository path issue - {verified_path}"

    repo = Path(verified_path)
    if not repo.exists() or not repo.is_dir():
        logger.warning("Analysis aborted: verified path is not a directory (%s)", verified_path)
        return f"❌ Error: Invalid repository path: {verified_path}"

    py_files = list(repo.rglob(file_pattern))
    py_files = [
        f
        for f in py_files
        if not EXCLUDED_PARTS.intersection(f.parts)
        and not f.name.startswith("test_")
        and not f.name.endswith("_test.py")
        and "tests" not in f.parts
    ]

    if not py_files:
        logger.info("No files matched pattern during analysis: %s", file_pattern)
        return f"⚠️ No Python files found matching pattern: {file_pattern}"

    manifest = discover_tech_stack_manifest(repo)
    surfaces = discover_testable_surfaces(repo)

    analysis = {"total_files": len(py_files), "files": []}
    for py_file in py_files[:50]:
        file_analysis = analyze_python_file(str(py_file))
        file_analysis["path"] = str(py_file.relative_to(repo))
        analysis["files"].append(file_analysis)

    total_functions = sum(len(f.get("functions", [])) for f in analysis["files"])
    total_classes = sum(len(f.get("classes", [])) for f in analysis["files"])
    recommended_targets = discover_unit_test_targets(repo)

    return (
        "📊 Codebase Analysis Complete\n\n"
        f"📁 Files analyzed: {analysis['total_files']}\n"
        f"⚡ Functions found: {total_functions}\n"
        f"🏗️ Classes found: {total_classes}\n"
        f"\n🧭 TechStackManifest:\n{json.dumps(manifest.__dict__, indent=2)}\n"
        f"\n🗺️ Testable Surfaces:\n{json.dumps(surfaces, indent=2)}\n"
        f"\n🎯 Recommended unit test targets:\n" + "\n".join(f"- {target}" for target in recommended_targets)
    )
