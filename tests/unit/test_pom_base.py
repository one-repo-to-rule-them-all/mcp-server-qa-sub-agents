"""Unit tests for the Page Object Model base class (no browser required).

Tests the POM framework logic using mocked Playwright Page objects.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.e2e.pages.base_page import BasePage
from tests.e2e.pages.login_page import LoginPage
from tests.e2e.pages.dashboard_page import DashboardPage


@pytest.mark.unit
class TestBasePageInit:
    """Verify BasePage construction and URL building."""

    def test_default_base_url(self):
        page = MagicMock()
        bp = BasePage(page)
        assert bp.base_url == "http://localhost:3000"

    def test_custom_base_url_strips_trailing_slash(self):
        page = MagicMock()
        bp = BasePage(page, "https://example.com/")
        assert bp.base_url == "https://example.com"

    def test_navigate_builds_full_url(self):
        page = MagicMock()
        bp = BasePage(page, "https://example.com")
        bp.path = "/about"
        bp.navigate()
        page.goto.assert_called_once_with("https://example.com/about")

    def test_title_delegates_to_page(self):
        page = MagicMock()
        page.title.return_value = "My App"
        bp = BasePage(page)
        assert bp.title == "My App"

    def test_url_delegates_to_page(self):
        page = MagicMock()
        page.url = "https://example.com/page"
        bp = BasePage(page)
        assert bp.url == "https://example.com/page"


@pytest.mark.unit
class TestSelfHealingFind:
    """Verify the self-healing locator fallback chain."""

    def test_returns_primary_when_visible(self):
        page = MagicMock()
        locator = MagicMock()
        locator.first.wait_for = MagicMock()
        page.locator.return_value = locator

        bp = BasePage(page)
        result = bp.find('[data-testid="btn"]')

        assert result is locator
        page.locator.assert_called_once_with('[data-testid="btn"]')

    def test_falls_back_when_primary_fails(self):
        page = MagicMock()
        primary_locator = MagicMock()
        primary_locator.first.wait_for.side_effect = TimeoutError("not found")

        fallback_locator = MagicMock()
        fallback_locator.first.wait_for = MagicMock()

        page.locator.side_effect = [primary_locator, fallback_locator]

        bp = BasePage(page)
        result = bp.find('[data-testid="btn"]', fallbacks=('button.submit',))

        assert result is fallback_locator

    def test_raises_timeout_when_all_fail(self):
        page = MagicMock()
        locator = MagicMock()
        locator.first.wait_for.side_effect = TimeoutError("nope")
        page.locator.return_value = locator

        bp = BasePage(page)

        with pytest.raises(TimeoutError, match="exhausted"):
            bp.find('[data-testid="btn"]', fallbacks=('button', '.btn'))

    def test_tries_all_selectors_in_order(self):
        page = MagicMock()
        failing = MagicMock()
        failing.first.wait_for.side_effect = TimeoutError()
        success = MagicMock()
        success.first.wait_for = MagicMock()

        page.locator.side_effect = [failing, failing, success]

        bp = BasePage(page)
        result = bp.find("primary", fallbacks=("fallback1", "fallback2"))

        assert result is success
        assert page.locator.call_count == 3


@pytest.mark.unit
class TestLoginPagePOM:
    """Verify LoginPage actions delegate to self-healing find."""

    def test_login_page_path(self):
        page = MagicMock()
        lp = LoginPage(page)
        assert lp.path == "/login"

    def test_login_fills_and_clicks(self):
        page = MagicMock()
        locator = MagicMock()
        locator.first = MagicMock()
        page.locator.return_value = locator

        lp = LoginPage(page)
        lp.login("user", "pass")

        # Should have called fill for username, fill for password, click for submit
        assert locator.first.fill.call_count == 2
        assert locator.first.click.call_count == 1


@pytest.mark.unit
class TestDashboardPagePOM:
    """Verify DashboardPage delegates to self-healing find."""

    def test_dashboard_page_path(self):
        page = MagicMock()
        dp = DashboardPage(page)
        assert dp.path == "/dashboard"

    def test_get_heading_text(self):
        page = MagicMock()
        locator = MagicMock()
        locator.first.inner_text.return_value = "Dashboard"
        page.locator.return_value = locator

        dp = DashboardPage(page)
        assert dp.get_heading_text() == "Dashboard"
