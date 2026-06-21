"""
Shared Pytest Fixtures & Mocks

Configures sys.path dynamically, sets up isolated SQLite databases for test runs,
and mocks Google GenAI Client operations.
"""

import sys
import os
from pathlib import Path
import pytest
import tempfile

# Insert package root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.manager import DatabaseManager


@pytest.fixture
def temp_db_file():
    """Generates an isolated database file path that is automatically cleaned up."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


@pytest.fixture
def db(temp_db_file):
    """Instantiates a fresh database manager instance targeting the temp file."""
    manager = DatabaseManager(temp_db_file)
    return manager


@pytest.fixture
def mock_genai_client(mocker):
    """Mocks the Google GenAI SDK client to prevent external API calls."""
    mock_client = mocker.MagicMock()
    
    # Mock client.models.generate_content responses
    mock_response = mocker.MagicMock()
    mock_response.text = "Gemini generated content"
    mock_client.models.generate_content.return_value = mock_response
    
    mocker.patch("google.genai.Client", return_value=mock_client)
    return mock_client
