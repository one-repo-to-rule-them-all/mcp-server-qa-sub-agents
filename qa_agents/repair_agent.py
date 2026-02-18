"""Healer agent for parsing failures and applying self-healing patches."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("qa-council-server.repair-agent")


def _fuzzy_selector_replacement(selector: str, dom_snapshot: str) -> str:
    """Very lightweight selector healing from DOM snapshot."""
    if selector in dom_snapshot:
        return selector

    id_candidates = re.findall(r"id=['\"]([^'\"]+)['\"]", dom_snapshot)
    class_candidates = re.findall(r"class=['\"]([^'\"]+)['\"]", dom_snapshot)
    if id_candidates:
        return f"#{id_candidates[0]}"
    if class_candidates:
        return "." + class_candidates[0].split()[0]
    return selector


def _patch_page_objects(repo_path: str, broken_selector: str, healed_selector: str) -> list[str]:
    patched: list[str] = []
    pages_dir = Path(repo_path) / "tests" / "pages"
    if not pages_dir.exists():
        return patched

    for page_file in pages_dir.glob("**/*"):
        if page_file.suffix not in {".py", ".ts", ".tsx", ".js"}:
            continue
        content = page_file.read_text(encoding="utf-8", errors="ignore")
        if broken_selector not in content:
            continue
        page_file.write_text(content.replace(broken_selector, healed_selector), encoding="utf-8")
        patched.append(str(page_file.relative_to(repo_path)))
    return patched


async def repair_failing_tests(repo_path: str, test_output: str) -> str:
    """Analyze test failures and apply selector-healing patches when possible."""
    if not repo_path.strip():
        return "❌ Error: Repository path is required"
    if not test_output.strip():
        return "⚠️ No test output provided. Run execute_tests first to get failure details."

    match = re.search(r"FailurePayload:\n(\[.*?\])\n\n", test_output, re.DOTALL)
    payloads = []
    if match:
        try:
            payloads = json.loads(match.group(1))
        except json.JSONDecodeError:
            payloads = []

    if not payloads:
        return "✅ No structured failure payloads found - no healing action required."

    logs: list[str] = ["🔧 Self-Healing Report", ""]
    total_patches = 0
    for payload in payloads:
        selector = payload.get("selector", "#unknown")
        healed_selector = _fuzzy_selector_replacement(selector, payload.get("dom_snapshot", ""))
        patched_files = _patch_page_objects(repo_path, selector, healed_selector)
        total_patches += len(patched_files)
        logs.append(f"- Error: {payload.get('error', 'unknown')}")
        logs.append(f"  - Broken selector: {selector}")
        logs.append(f"  - Healed selector: {healed_selector}")
        logs.append(f"  - Patched files: {', '.join(patched_files) if patched_files else 'none'}")

    logs.append("")
    logs.append(f"✅ Healing completed with {total_patches} patched selector reference(s).")
    return "\n".join(logs)
