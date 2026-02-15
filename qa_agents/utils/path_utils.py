"""Filesystem path helpers for QA agents."""

from __future__ import annotations

import os
from pathlib import Path


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
