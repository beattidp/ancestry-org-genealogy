"""Unit tests for FamilySearchClient."""

import pytest
import httpx
from src.config import Settings
from src.familysearch.auth import SessionManager
from src.familysearch.client import (
    FamilySearchClient,
    FamilySearchAuthError,
    FamilySearchNotFoundError,
    FamilySearchAPIError,
)


def test_client_missing_headers():
    settings = Settings(FAMILYSEARCH_SESSION_ID="")
    client = FamilySearchClient(settings=settings)
    with pytest.raises(FamilySearchAuthError) as exc_info:
        client.get_current_user()
    assert "Authentication headers are missing" in str(exc_info.value)


def test_client_mock_dispatch(monkeypatch):
    """Test client handles successful 200 response."""
    settings = Settings(FAMILYSEARCH_SESSION_ID="valid_token")
    client = FamilySearchClient(settings=settings)

    def mock_request(self, method, url, **kwargs):
        return httpx.Response(
            status_code=200,
            json={"persons": [{"id": "TEST-123", "display": {"name": "Test Person"}}]},
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(httpx.Client, "request", mock_request)

    res = client.get_person("TEST-123")
    assert "persons" in res
    assert res["persons"][0]["id"] == "TEST-123"


def test_client_mock_404_not_found(monkeypatch):
    settings = Settings(FAMILYSEARCH_SESSION_ID="valid_token")
    client = FamilySearchClient(settings=settings)

    def mock_request(self, method, url, **kwargs):
        return httpx.Response(
            status_code=404,
            text="Not Found",
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(httpx.Client, "request", mock_request)

    with pytest.raises(FamilySearchNotFoundError):
        client.get_person("NON-EXISTENT")


def test_client_mock_401_auth_error(monkeypatch):
    settings = Settings(FAMILYSEARCH_SESSION_ID="expired_token")
    client = FamilySearchClient(settings=settings)

    def mock_request(self, method, url, **kwargs):
        return httpx.Response(
            status_code=401,
            text="Unauthorized",
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(httpx.Client, "request", mock_request)

    with pytest.raises(FamilySearchAuthError) as exc_info:
        client.get_current_user()
    assert "Authentication failed (401)" in str(exc_info.value)
