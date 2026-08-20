"""
Shared pytest fixtures and configuration.
Place service-level conftest.py files in each service's tests/ directory.
"""

import asyncio
import pytest


# Configure asyncio mode for all async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def anyio_backend():
    return "asyncio"
