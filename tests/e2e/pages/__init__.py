"""Page Object Model classes for E2E testing."""

from .base_page import BasePage
from .dashboard_page import DashboardPage
from .login_page import LoginPage

__all__ = ["BasePage", "DashboardPage", "LoginPage"]
