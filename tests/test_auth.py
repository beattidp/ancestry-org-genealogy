"""Unit tests for authentication and session management."""

from src.config import Settings
from src.familysearch.auth import SessionManager


def test_auth_headers_empty_token():
    settings = Settings(FAMILYSEARCH_SESSION_ID="")
    manager = SessionManager(settings)
    assert manager.get_auth_headers() == {}


def test_auth_headers_with_token():
    settings = Settings(FAMILYSEARCH_SESSION_ID="mock_token_12345")
    manager = SessionManager(settings)
    headers = manager.get_auth_headers()
    assert headers["Authorization"] == "Bearer mock_token_12345"
    assert "application/x-gedcomx-v1+json" in headers["Accept"]


def test_validate_session_missing_token():
    settings = Settings(FAMILYSEARCH_SESSION_ID="")
    manager = SessionManager(settings)
    status = manager.validate_session()
    assert not status.is_valid
    assert status.status_code == 0
    assert "No FAMILYSEARCH_SESSION_ID configured" in status.message
