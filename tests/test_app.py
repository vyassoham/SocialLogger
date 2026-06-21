"""
Streamlit App Integration Tests

Uses the Streamlit AppTest framework to verify rendering, tab initialization,
sidebar health status checks, and that no exceptions are raised during execution.
"""

import os
import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture(autouse=True)
def cleanup_default_db():
    """Cleans up the default database file generated during app tests."""
    yield
    db_file = "social_logger.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except OSError:
            pass


def test_app_renders_correctly():
    # 1. Initialize AppTest from app.py
    at = AppTest.from_file("app.py")
    
    # 2. Run app scripts (using a generous timeout)
    at.run(timeout=30)
    
    # 3. Assert no exceptions were thrown
    assert not at.exception, f"App execution threw an exception: {at.exception}"
    
    # 4. Verify main header text is correct
    assert len(at.title) > 0
    assert "Social Media" in at.title[0].value
    
    # 5. Check if tab widgets render
    assert len(at.tabs) >= 5
    
    # 6. Verify sidebar health indicators exist
    sidebar_md = "".join([m.value for m in at.sidebar.markdown])
    assert "System Health" in sidebar_md
    
    success_vals = [s.value for s in at.sidebar.success]
    assert "Scheduler: Active" in success_vals
    assert "Database: Connected" in success_vals
