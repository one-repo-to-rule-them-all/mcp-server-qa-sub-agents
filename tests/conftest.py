"""Test-layer conftest: markers, self-healing retry decorator, async helpers."""

from __future__ import annotations

import functools
import logging

import pytest

logger = logging.getLogger("qa-council-tests")


# ---------------------------------------------------------------------------
# Self-healing retry decorator for tests
# ---------------------------------------------------------------------------

def self_healing_retry(max_retries: int = 3):
    """Decorator that retries a failing test up to *max_retries* times.

    Intended for tests marked with ``@pytest.mark.self_healing``.  On each
    retry the failure reason is logged so the repair agent (or a human) can
    inspect what went wrong.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    logger.warning(
                        "Self-healing retry %d/%d for %s: %s",
                        attempt,
                        max_retries,
                        func.__name__,
                        exc,
                    )
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Pytest configuration hook – wire up markers
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Register custom markers so --strict-markers does not complain."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (multi-agent)")
    config.addinivalue_line("markers", "e2e: End-to-end Playwright tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")
    config.addinivalue_line("markers", "self_healing: Tests with self-healing retry capability")
