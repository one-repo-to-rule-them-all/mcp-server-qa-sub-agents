"""E2E conftest: Playwright browser fixtures and POM factory."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def browser_context_args():
    """Default browser context options for all E2E tests."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture()
def base_url():
    """Override with --base-url or default to localhost."""
    return "http://localhost:3000"
