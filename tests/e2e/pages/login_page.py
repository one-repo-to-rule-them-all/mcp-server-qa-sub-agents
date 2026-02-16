"""Login page object for E2E testing."""

from __future__ import annotations

from .base_page import BasePage


class LoginPage(BasePage):
    """Page object for the login/authentication screen.

    Self-healing selectors: each action tries a primary selector then
    common fallbacks (data-testid, aria-role, name attribute).
    """

    path = "/login"

    # Selector constants – primary + fallbacks
    _USERNAME = '[data-testid="username-input"]'
    _USERNAME_FALLBACKS = ('input[name="username"]', 'input[type="text"]')

    _PASSWORD = '[data-testid="password-input"]'
    _PASSWORD_FALLBACKS = ('input[name="password"]', 'input[type="password"]')

    _SUBMIT = '[data-testid="login-button"]'
    _SUBMIT_FALLBACKS = ('button[type="submit"]', 'text=Log in', 'text=Sign in')

    _ERROR_MSG = '[data-testid="login-error"]'
    _ERROR_FALLBACKS = ('[role="alert"]', '.error-message')

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def enter_username(self, username: str) -> None:
        locator = self.find(self._USERNAME, self._USERNAME_FALLBACKS)
        locator.first.fill(username)

    def enter_password(self, password: str) -> None:
        locator = self.find(self._PASSWORD, self._PASSWORD_FALLBACKS)
        locator.first.fill(password)

    def click_login(self) -> None:
        locator = self.find(self._SUBMIT, self._SUBMIT_FALLBACKS)
        locator.first.click()

    def login(self, username: str, password: str) -> None:
        """Convenience: fill both fields and submit."""
        self.enter_username(username)
        self.enter_password(password)
        self.click_login()

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    def expect_error_message(self, text: str) -> None:
        locator = self.find(self._ERROR_MSG, self._ERROR_FALLBACKS)
        from playwright.sync_api import expect
        expect(locator.first).to_contain_text(text)

    def expect_redirected_to_dashboard(self) -> None:
        self.page.wait_for_url("**/dashboard**", timeout=10_000)
