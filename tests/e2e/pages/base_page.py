"""Base Page Object with self-healing locator support.

Implements the Page Object Model (POM) pattern for Playwright E2E tests.
Each page class inherits from BasePage and exposes high-level actions
instead of raw selectors, making tests resilient to UI changes.

Self-healing: ``find()`` tries a primary locator, then falls back through
a list of alternatives.  Successful fallbacks are logged so the team can
update the canonical locator in future maintenance passes.
"""

from __future__ import annotations

import logging
from typing import Sequence

from playwright.sync_api import Locator, Page, expect

logger = logging.getLogger("qa-council.pom")


class BasePage:
    """Abstract base for all page objects."""

    # Subclasses should override with the page-specific path segment.
    path: str = "/"

    def __init__(self, page: Page, base_url: str = "http://localhost:3000") -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self) -> None:
        """Go to the page's canonical URL."""
        url = f"{self.base_url}{self.path}"
        logger.info("Navigating to %s", url)
        self.page.goto(url)

    def reload(self) -> None:
        self.page.reload()

    @property
    def title(self) -> str:
        return self.page.title()

    @property
    def url(self) -> str:
        return self.page.url

    # ------------------------------------------------------------------
    # Self-healing locator
    # ------------------------------------------------------------------

    def find(
        self,
        primary: str,
        fallbacks: Sequence[str] = (),
        *,
        timeout: float = 5_000,
    ) -> Locator:
        """Locate an element with self-healing fallback chain.

        Parameters
        ----------
        primary:
            The preferred Playwright selector (CSS, text=, data-testid=, etc.).
        fallbacks:
            Ordered sequence of alternative selectors to try when *primary*
            is not visible within *timeout* ms.
        timeout:
            Milliseconds to wait for each selector before trying the next.

        Returns
        -------
        Locator
            The first locator whose element is visible on the page.

        Raises
        ------
        TimeoutError
            When none of the selectors resolve to a visible element.
        """
        all_selectors = [primary, *fallbacks]
        last_error: Exception | None = None

        for selector in all_selectors:
            try:
                locator = self.page.locator(selector)
                locator.first.wait_for(state="visible", timeout=timeout)
                if selector != primary:
                    logger.warning(
                        "Self-healed: primary '%s' failed, used fallback '%s'",
                        primary,
                        selector,
                    )
                return locator
            except Exception as exc:
                last_error = exc
                logger.debug("Selector '%s' not visible, trying next fallback", selector)

        raise TimeoutError(
            f"Self-healing exhausted all selectors: {all_selectors}"
        ) from last_error

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def wait_for_load(self, state: str = "networkidle") -> None:
        """Wait until the page reaches the given load state."""
        self.page.wait_for_load_state(state)

    def screenshot(self, path: str = "screenshot.png") -> bytes:
        """Capture a full-page screenshot."""
        return self.page.screenshot(path=path, full_page=True)

    def get_text(self, selector: str) -> str:
        """Return the inner text of the first matching element."""
        return self.page.locator(selector).first.inner_text()

    def click(self, selector: str, **kwargs) -> None:
        """Click the first element matching *selector*."""
        self.page.locator(selector).first.click(**kwargs)

    def fill(self, selector: str, value: str) -> None:
        """Fill a form input."""
        self.page.locator(selector).first.fill(value)

    def expect_visible(self, selector: str, *, timeout: float = 5_000) -> None:
        """Assert that an element is visible."""
        expect(self.page.locator(selector).first).to_be_visible(timeout=timeout)

    def expect_text(self, selector: str, text: str, *, timeout: float = 5_000) -> None:
        """Assert that an element contains the given text."""
        expect(self.page.locator(selector).first).to_contain_text(text, timeout=timeout)
