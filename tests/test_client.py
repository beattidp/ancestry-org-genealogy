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


def test_add_or_update_person_fact(monkeypatch):
    """Test fact update creates valid GEDCOM X JSON and handles 204 response."""
    settings = Settings(FAMILYSEARCH_SESSION_ID="valid_token")
    client = FamilySearchClient(settings=settings)

    captured_requests = []

    def mock_request(self, method, url, **kwargs):
        captured_requests.append({"method": method, "url": str(url), "json": kwargs.get("json")})
        return httpx.Response(status_code=204, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", mock_request)

    res = client.add_or_update_person_fact(
        pid="9ZMG-JSD",
        fact_type="Birth",
        date_original="about 1605",
        place_original="Liberton, Midlothian, Scotland",
        change_message="Verified via ScotlandsPeople parish register #693",
        place_coordinates=(55.9142, -3.1611),
    )

    assert res == {}
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req["method"] == "POST"
    assert "/platform/tree/persons/9ZMG-JSD" in req["url"]
    payload = req["json"]
    assert "persons" in payload
    assert payload["persons"][0]["id"] == "9ZMG-JSD"
    assert payload["persons"][0]["facts"][0]["type"] == "http://gedcomx.org/Birth"
    assert payload["persons"][0]["facts"][0]["date"]["original"] == "about 1605"
    assert payload["persons"][0]["facts"][0]["place"]["original"] == "Liberton, Midlothian, Scotland"
    assert payload["places"][0]["latitude"] == 55.9142
    assert payload["places"][0]["longitude"] == -3.1611
    assert payload["persons"][0]["facts"][0]["attribution"]["changeMessage"] == "Verified via ScotlandsPeople parish register #693"


def test_write_missing_change_message_raises():
    """Verify that omitting changeMessage raises ValueError before dispatch."""
    settings = Settings(FAMILYSEARCH_SESSION_ID="valid_token")
    client = FamilySearchClient(settings=settings)

    with pytest.raises(ValueError) as exc:
        client.add_or_update_person_fact(
            pid="9ZMG-JSD",
            fact_type="Birth",
            change_message="   ",
        )
    assert "changeMessage justification is strictly required" in str(exc.value)


def test_create_source_description_and_attach(monkeypatch):
    """Test source description creation and linking to person."""
    settings = Settings(FAMILYSEARCH_SESSION_ID="valid_token")
    client = FamilySearchClient(settings=settings)

    calls = []

    def mock_request(self, method, url, **kwargs):
        calls.append({"method": method, "url": str(url), "json": kwargs.get("json")})
        if str(url).endswith("/platform/sources/descriptions"):
            headers = {"Location": "https://api.familysearch.org/platform/sources/descriptions/SD-999"}
            return httpx.Response(status_code=201, headers=headers, request=httpx.Request(method, url))
        return httpx.Response(status_code=204, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", mock_request)

    res = client.add_person_source_citation(
        pid="9ZMG-JSD",
        url="https://www.loc.gov/resource/sn96077385/1888-03-09/ed-1/?sp=4",
        title="1888 Owosso Times probate announcement",
        citation="The times (Owosso, Mich.), March 9, 1888, Image 4",
        change_message="Verified via 1888 Owosso Times probate announcement",
    )

    assert res == {}
    assert len(calls) == 2
    assert "/platform/sources/descriptions" in calls[0]["url"]
    assert calls[0]["json"]["sourceDescriptions"][0]["about"] == "https://www.loc.gov/resource/sn96077385/1888-03-09/ed-1/?sp=4"
    assert "/platform/tree/persons/9ZMG-JSD" in calls[1]["url"]
    assert calls[1]["json"]["persons"][0]["sources"][0]["description"] == "https://api.familysearch.org/platform/sources/descriptions/SD-999"


def test_create_relationship(monkeypatch):
    """Test relationship creation payload."""
    settings = Settings(FAMILYSEARCH_SESSION_ID="valid_token")
    client = FamilySearchClient(settings=settings)

    captured = []

    def mock_request(self, method, url, **kwargs):
        captured.append(kwargs.get("json"))
        return httpx.Response(status_code=201, headers={"Location": "https://api.familysearch.org/platform/tree/relationships/R-123"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", mock_request)

    res = client.create_relationship(
        rel_type="ParentChild",
        person1_pid="P-FATHER",
        person2_pid="P-CHILD",
        change_message="Verified via ScotlandsPeople parish register #693",
    )
    assert res.get("location") == "https://api.familysearch.org/platform/tree/relationships/R-123"
    assert len(captured) == 1
    rel = captured[0]["relationships"][0]
    assert rel["type"] == "http://gedcomx.org/ParentChild"
    assert rel["person1"]["resourceId"] == "P-FATHER"
    assert rel["person2"]["resourceId"] == "P-CHILD"


def test_create_person_duplicate_detection(monkeypatch):
    """Test duplicate detection stops creation when potential matches exist."""
    settings = Settings(FAMILYSEARCH_SESSION_ID="valid_token")
    client = FamilySearchClient(settings=settings)

    def mock_request(self, method, url, **kwargs):
        if "/platform/tree/matches" in str(url):
            return httpx.Response(
                status_code=200,
                json={"entries": [{"id": "MATCH-1", "title": "Existing John Doe"}]},
                request=httpx.Request(method, url),
            )
        return httpx.Response(status_code=201, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", mock_request)

    person_payload = {
        "persons": [
            {
                "names": [
                    {
                        "nameForms": [
                            {
                                "parts": [
                                    {"type": "http://gedcomx.org/Given", "value": "John"},
                                    {"type": "http://gedcomx.org/Surname", "value": "Doe"},
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }

    with pytest.raises(ValueError) as exc:
        client.create_person(person_payload, change_message="New discovery", check_duplicates=True)
    assert "Potential duplicate matches found" in str(exc.value)


def test_write_tree_write_permission_error(monkeypatch):
    """Test 403 error on write gives explicit Tree Write hint."""
    settings = Settings(FAMILYSEARCH_SESSION_ID="readonly_token")
    client = FamilySearchClient(settings=settings)

    def mock_request(self, method, url, **kwargs):
        return httpx.Response(
            status_code=403,
            text="Forbidden: Insufficient scope",
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(httpx.Client, "request", mock_request)

    with pytest.raises(FamilySearchAuthError) as exc:
        client.add_or_update_person_fact(
            pid="TEST-1",
            fact_type="Birth",
            change_message="Test note",
        )
    assert "Tree Write" in str(exc.value)

