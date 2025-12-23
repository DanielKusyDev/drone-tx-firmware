"""
Pytest configuration and shared fixtures.

This file contains fixtures that are available to all test modules.
"""

import pytest


# Configure pytest-asyncio
@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for asyncio tests."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()


# Add custom markers to tests based on test class names
def pytest_collection_modifyitems(config, items):
    """
    Automatically add markers based on test location and names.

    This allows running specific test categories:
    - pytest -m unit
    - pytest -m integration
    - pytest -m "not slow"
    """
    for item in items:
        # Add unit marker to most tests by default
        if "integration" not in item.nodeid.lower():
            item.add_marker(pytest.mark.unit)

        # Add integration marker to integration tests
        if "integration" in item.nodeid.lower():
            item.add_marker(pytest.mark.integration)

        # Add parser marker to parser tests
        if "parser" in item.nodeid.lower():
            item.add_marker(pytest.mark.parser)


def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Register custom markers (in addition to pytest.ini)
    config.addinivalue_line("markers", "unit: unit tests")
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line("markers", "parser: parser-specific tests")
