import logging
import pytest
from unittest.mock import MagicMock

# Configure logging for tests
def pytest_configure(config):
    """Set up logging configuration when pytest starts."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

@pytest.fixture
def caplog(caplog):
    """Enhance the built-in caplog fixture with proper log level."""
    caplog.set_level(logging.DEBUG)
    return caplog

@pytest.fixture
def test_logger():
    """Provide a logger fixture for tests to use."""
    logger = logging.getLogger('test')
    logger.setLevel(logging.DEBUG)
    return logger

@pytest.fixture
def db_session():
    """Provide a mock database session for tests that don't need a real DB."""
    return MagicMock()