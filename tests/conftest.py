"""Shared test setup."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture(scope="session")
def dash_app() -> Any:
    """The Dash app with all pages registered (importing app.py creates it)."""
    import app

    return app.app
