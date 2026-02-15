"""Pytest configuration for E2E tests with Playwright."""
import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="session")
def browser():
    """Launch browser for E2E tests."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture(scope="function")
def page(browser):
    """Create a new page for each test."""
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080}
    )
    page = context.new_page()
    yield page
    page.close()
    context.close()

@pytest.fixture
def base_url():
    """Base URL for the application."""
    return "http://localhost:8000"
