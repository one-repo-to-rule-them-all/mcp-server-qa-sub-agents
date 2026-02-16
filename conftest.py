"""Root conftest: shared fixtures available to all test layers."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal git-like repo directory with sample Python source."""
    repo = tmp_path / "sample_repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    # Backend Python source
    backend = repo / "backend"
    backend.mkdir()
    (backend / "__init__.py").write_text("")
    (backend / "main.py").write_text(
        textwrap.dedent("""\
            import logging

            logger = logging.getLogger(__name__)


            def health_check():
                return {"status": "ok"}


            class ItemService:
                def __init__(self, db=None):
                    self.db = db

                def list_items(self):
                    return []

                def create_item(self, name, value=0):
                    return {"name": name, "value": value}
        """),
    )

    # Frontend React source
    frontend_src = repo / "frontend" / "src"
    frontend_src.mkdir(parents=True)
    (frontend_src / "App.tsx").write_text(
        textwrap.dedent("""\
            import React from 'react';

            function App() {
                return <div data-testid="app-root">Hello</div>;
            }

            export default App;
        """),
    )

    # Tests directory
    (repo / "tests" / "unit").mkdir(parents=True)
    (repo / "tests" / "e2e").mkdir(parents=True)

    return repo


@pytest.fixture()
def sample_python_file(tmp_path: Path) -> Path:
    """Create a standalone Python file with functions and classes for AST testing."""
    source = tmp_path / "sample.py"
    source.write_text(
        textwrap.dedent("""\
            import os
            from pathlib import Path


            def public_function(name: str, count: int = 1):
                return name * count


            def _private_helper():
                pass


            class MyService:
                def __init__(self, config=None):
                    self.config = config or {}

                def run(self):
                    return True

                def _internal(self):
                    pass


            async def async_handler(request):
                return {"ok": True}
        """),
    )
    return source


@pytest.fixture()
def mock_github_token():
    """Provide a fake GITHUB_TOKEN for tests that need authenticated API calls."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_fake_test_token_1234567890"}):
        yield "ghp_fake_test_token_1234567890"


@pytest.fixture()
def clean_env():
    """Ensure GitHub token env vars are cleared for isolation."""
    env_vars = ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT")
    with patch.dict(os.environ, {k: "" for k in env_vars}, clear=False):
        yield
