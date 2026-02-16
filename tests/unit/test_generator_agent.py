"""Unit tests for qa_agents.generator_agent – test generation for Python and React."""

from __future__ import annotations

from pathlib import Path

import pytest

from qa_agents.generator_agent import generate_e2e_tests, generate_unit_tests


@pytest.mark.unit
class TestGenerateUnitTestsPython:
    """Verify Python unit test scaffold generation."""

    @pytest.mark.asyncio
    async def test_rejects_empty_repo_path(self):
        result = await generate_unit_tests("", "backend/main.py")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_rejects_empty_target_file(self, tmp_repo):
        result = await generate_unit_tests(str(tmp_repo), "")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_generates_python_unit_tests(self, tmp_repo):
        result = await generate_unit_tests(str(tmp_repo), "backend/main.py")

        assert "✅" in result
        assert "Unit tests generated" in result

        test_file = tmp_repo / "tests" / "unit" / "test_main.py"
        assert test_file.exists()

        content = test_file.read_text()
        assert "import pytest" in content
        assert "from unittest.mock import" in content
        assert "health_check" in content
        assert "TestItemService" in content

    @pytest.mark.asyncio
    async def test_generated_tests_have_fixtures(self, tmp_repo):
        await generate_unit_tests(str(tmp_repo), "backend/main.py")

        test_file = tmp_repo / "tests" / "unit" / "test_main.py"
        content = test_file.read_text()

        assert "@pytest.fixture" in content

    @pytest.mark.asyncio
    async def test_returns_error_for_missing_file(self, tmp_repo):
        result = await generate_unit_tests(str(tmp_repo), "missing/file.py")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_skips_unsupported_file_type(self, tmp_repo):
        # Create a .go file
        go_file = tmp_repo / "main.go"
        go_file.write_text("package main")

        result = await generate_unit_tests(str(tmp_repo), "main.go")
        assert "⚠️" in result


@pytest.mark.unit
class TestGenerateUnitTestsReact:
    """Verify React/TSX unit test scaffold generation (RTL + Vitest)."""

    @pytest.mark.asyncio
    async def test_generates_react_unit_tests(self, tmp_repo):
        result = await generate_unit_tests(str(tmp_repo), "frontend/src/App.tsx")

        assert "✅" in result
        assert "React" in result

        test_file = tmp_repo / "tests" / "unit" / "App.test.tsx"
        assert test_file.exists()

        content = test_file.read_text()
        assert "@testing-library/react" in content
        assert "userEvent" in content
        assert "vi" in content
        assert "renders without crashing" in content

    @pytest.mark.asyncio
    async def test_react_test_imports_use_alias(self, tmp_repo):
        await generate_unit_tests(str(tmp_repo), "frontend/src/App.tsx")

        test_file = tmp_repo / "tests" / "unit" / "App.test.tsx"
        content = test_file.read_text()

        # Should use @/ path alias for frontend/src imports
        assert '@/' in content

    @pytest.mark.asyncio
    async def test_react_test_has_interaction_test(self, tmp_repo):
        await generate_unit_tests(str(tmp_repo), "frontend/src/App.tsx")

        test_file = tmp_repo / "tests" / "unit" / "App.test.tsx"
        content = test_file.read_text()

        assert "supports user interaction" in content
        assert "userEvent.setup()" in content

    @pytest.mark.asyncio
    async def test_react_test_has_mock_verification(self, tmp_repo):
        await generate_unit_tests(str(tmp_repo), "frontend/src/App.tsx")

        test_file = tmp_repo / "tests" / "unit" / "App.test.tsx"
        content = test_file.read_text()

        assert "vi.fn()" in content
        assert "toHaveBeenCalledTimes" in content


@pytest.mark.unit
class TestGenerateE2ETests:
    """Verify Playwright E2E test scaffold generation."""

    @pytest.mark.asyncio
    async def test_rejects_empty_repo_path(self):
        result = await generate_e2e_tests("", "http://localhost:3000", "app")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_rejects_empty_base_url(self, tmp_repo):
        result = await generate_e2e_tests(str(tmp_repo), "", "app")
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_generates_e2e_test_file(self, tmp_repo):
        result = await generate_e2e_tests(
            str(tmp_repo), "http://localhost:3000", "media_tracker",
        )

        assert "✅" in result

        test_file = tmp_repo / "tests" / "e2e" / "test_media_tracker_e2e.py"
        assert test_file.exists()

        content = test_file.read_text()
        assert "playwright" in content
        assert "page.goto" in content
        assert "test_media_tracker_page_loads" in content

    @pytest.mark.asyncio
    async def test_e2e_uses_playwright_expect(self, tmp_repo):
        await generate_e2e_tests(str(tmp_repo), "http://localhost:3000", "app")

        test_file = tmp_repo / "tests" / "e2e" / "test_app_e2e.py"
        content = test_file.read_text()

        assert "from playwright.sync_api import" in content
        assert "expect" in content
