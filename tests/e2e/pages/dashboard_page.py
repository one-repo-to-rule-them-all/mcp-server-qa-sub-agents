"""Dashboard page object for E2E testing."""

from __future__ import annotations

from .base_page import BasePage


class DashboardPage(BasePage):
    """Page object for the main dashboard/home screen.

    Self-healing selectors with data-testid primary, semantic fallbacks.
    """

    path = "/dashboard"

    # Selector constants
    _HEADING = '[data-testid="dashboard-heading"]'
    _HEADING_FALLBACKS = ("h1", '[role="heading"]')

    _NAV = '[data-testid="main-nav"]'
    _NAV_FALLBACKS = ("nav", '[role="navigation"]')

    _USER_MENU = '[data-testid="user-menu"]'
    _USER_MENU_FALLBACKS = ('[aria-label="User menu"]', ".user-menu")

    _CONTENT_AREA = '[data-testid="content-area"]'
    _CONTENT_FALLBACKS = ("main", '[role="main"]')

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def get_heading_text(self) -> str:
        locator = self.find(self._HEADING, self._HEADING_FALLBACKS)
        return locator.first.inner_text()

    def open_user_menu(self) -> None:
        locator = self.find(self._USER_MENU, self._USER_MENU_FALLBACKS)
        locator.first.click()

    def navigate_to(self, link_text: str) -> None:
        """Click a navigation link by its visible text."""
        nav = self.find(self._NAV, self._NAV_FALLBACKS)
        nav.get_by_text(link_text).click()

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    def expect_loaded(self) -> None:
        """Assert the dashboard content area is visible."""
        self.find(self._CONTENT_AREA, self._CONTENT_FALLBACKS)

    def expect_heading(self, text: str) -> None:
        locator = self.find(self._HEADING, self._HEADING_FALLBACKS)
        from playwright.sync_api import expect
        expect(locator.first).to_contain_text(text)

    def expect_nav_visible(self) -> None:
        self.find(self._NAV, self._NAV_FALLBACKS)
