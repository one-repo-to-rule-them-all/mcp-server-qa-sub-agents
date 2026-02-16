"""E2E tests using Page Object Model for web application testing.

These tests demonstrate the POM pattern with self-healing locators.
They require a running application and Playwright browsers installed.
Run with: pytest tests/e2e/ --base-url=http://localhost:3000
"""

from __future__ import annotations

import pytest

from .pages.base_page import BasePage
from .pages.dashboard_page import DashboardPage
from .pages.login_page import LoginPage


@pytest.mark.e2e
class TestLoginFlow:
    """E2E scenarios for the login page using POM."""

    @pytest.fixture()
    def login_page(self, page, base_url):
        lp = LoginPage(page, base_url)
        lp.navigate()
        return lp

    def test_page_loads(self, login_page):
        """Login page should render without errors."""
        assert login_page.url.endswith("/login")

    def test_successful_login_redirects(self, login_page):
        """Valid credentials should redirect to dashboard."""
        login_page.login("admin", "password123")
        login_page.expect_redirected_to_dashboard()

    def test_invalid_credentials_shows_error(self, login_page):
        """Bad credentials should show an error message."""
        login_page.login("wrong_user", "wrong_pass")
        login_page.expect_error_message("Invalid")


@pytest.mark.e2e
class TestDashboard:
    """E2E scenarios for the dashboard using POM."""

    @pytest.fixture()
    def dashboard(self, page, base_url):
        dp = DashboardPage(page, base_url)
        dp.navigate()
        return dp

    def test_dashboard_loads(self, dashboard):
        """Dashboard should render the main content area."""
        dashboard.expect_loaded()

    def test_heading_visible(self, dashboard):
        """Dashboard heading should be present and non-empty."""
        text = dashboard.get_heading_text()
        assert len(text) > 0

    def test_navigation_present(self, dashboard):
        """Navigation should be visible on the dashboard."""
        dashboard.expect_nav_visible()


@pytest.mark.e2e
class TestSelfHealingLocators:
    """Demonstrate self-healing locator capability of the POM base."""

    @pytest.fixture()
    def base(self, page, base_url):
        bp = BasePage(page, base_url)
        bp.navigate()
        return bp

    def test_page_has_title(self, base):
        """Any page should have a non-empty title."""
        assert len(base.title) > 0

    def test_screenshot_capture(self, base, tmp_path):
        """Screenshot helper should produce a file."""
        screenshot_path = str(tmp_path / "test_screenshot.png")
        result = base.screenshot(screenshot_path)
        assert isinstance(result, bytes)
        assert len(result) > 0
