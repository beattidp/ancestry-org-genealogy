"""FamilySearch GEDCOM X Platform API client."""

from typing import Any
import httpx

from src.config import Settings, get_settings
from src.familysearch.auth import SessionManager


class FamilySearchAPIError(Exception):
    """Base exception for FamilySearch API failures."""

    def __init__(self, message: str, status_code: int = 0, response_text: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class FamilySearchAuthError(FamilySearchAPIError):
    """Raised when authentication fails or session expires (401/403)."""


class FamilySearchNotFoundError(FamilySearchAPIError):
    """Raised when a requested resource (person, record) is not found (404)."""


class FamilySearchClient:
    """Synchronous REST client for FamilySearch Platform API."""

    def __init__(
        self,
        session_manager: SessionManager | None = None,
        settings: Settings | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_manager = session_manager or SessionManager(self.settings)
        self.timeout = timeout
        self.base_url = self.settings.base_url

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Executes an authenticated HTTP request against FamilySearch API."""
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        headers = self.session_manager.get_auth_headers()

        if not headers:
            raise FamilySearchAuthError(
                "Authentication headers are missing. Provide a valid FAMILYSEARCH_SESSION_ID in .env."
            )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=headers,
                )

            if response.status_code == 200:
                if response.content:
                    return response.json()
                return {}

            if response.status_code == 204:
                return {}

            if response.status_code in (401, 403):
                raise FamilySearchAuthError(
                    f"Authentication failed ({response.status_code}): Session token is invalid or expired. "
                    "Please refresh your fssessionid from familysearch.org and update .env.",
                    status_code=response.status_code,
                    response_text=response.text,
                )

            if response.status_code == 404:
                raise FamilySearchNotFoundError(
                    f"Resource not found ({response.status_code}) at {path}.",
                    status_code=response.status_code,
                    response_text=response.text,
                )

            raise FamilySearchAPIError(
                f"FamilySearch API request failed with status {response.status_code}: {response.text[:300]}",
                status_code=response.status_code,
                response_text=response.text,
            )

        except httpx.RequestError as exc:
            raise FamilySearchAPIError(f"HTTP transport error while requesting {url}: {exc}") from exc

    # -------------------------------------------------------------------------
    # Identity & Account
    # -------------------------------------------------------------------------

    def get_current_user(self) -> dict[str, Any]:
        """Retrieves details of the authenticated user."""
        return self._request("GET", "/platform/users/current")

    # -------------------------------------------------------------------------
    # Family Tree: Person & Relationships
    # -------------------------------------------------------------------------

    def get_person(self, pid: str) -> dict[str, Any]:
        """Fetches full GEDCOM X payload for a tree person by PID (e.g. 'KW37-W3V')."""
        return self._request("GET", f"/platform/tree/persons/{pid}")

    def get_ancestry(
        self,
        pid: str,
        generations: int = 4,
        person_details: bool = True,
        marriage_details: bool = True,
    ) -> dict[str, Any]:
        """Retrieves multi-generational ancestry pedigree for an individual."""
        params: dict[str, Any] = {"person": pid, "generations": generations}
        if person_details:
            params["personDetails"] = "true"
        if marriage_details:
            params["marriageDetails"] = "true"
        return self._request("GET", "/platform/tree/ancestry", params=params)

    def get_person_parents(self, pid: str) -> dict[str, Any]:
        """Retrieves parent relationships for a person."""
        return self._request("GET", f"/platform/tree/persons/{pid}/parents")

    def get_person_spouses(self, pid: str) -> dict[str, Any]:
        """Retrieves spouse relationships for a person."""
        return self._request("GET", f"/platform/tree/persons/{pid}/spouses")

    def get_person_children(self, pid: str) -> dict[str, Any]:
        """Retrieves child relationships for a person."""
        return self._request("GET", f"/platform/tree/persons/{pid}/children")

    # -------------------------------------------------------------------------
    # Sources, Evidence & Matches (GPS Validation)
    # -------------------------------------------------------------------------

    def get_person_sources(self, pid: str) -> dict[str, Any]:
        """Retrieves all attached source descriptions and citations for a person."""
        return self._request("GET", f"/platform/tree/persons/{pid}/sources")

    def get_person_matches(self, pid: str, collection: str = "records") -> dict[str, Any]:
        """Retrieves algorithmic record hints or duplicate matches for a person.

        Args:
            pid: Person ID (PID)
            collection: 'records' (historical records archive) or 'tree' (duplicate profiles).
        """
        params = {"collection": collection}
        return self._request("GET", f"/platform/tree/persons/{pid}/matches", params=params)

    def get_person_changes(self, pid: str) -> dict[str, Any]:
        """Retrieves the full chronological change log and merge audit trail for a person."""
        return self._request("GET", f"/platform/tree/persons/{pid}/changes")

    # -------------------------------------------------------------------------
    # Historical Records Search
    # -------------------------------------------------------------------------

    def search_records(self, query_params: dict[str, Any]) -> dict[str, Any]:
        """Searches indexed historical records.

        Common query parameter keys:
            - q.givenName: First/given name
            - q.surname: Last name
            - q.birth.date: Birth year or range
            - q.birth.place: Birth locality/state/country
            - q.death.date: Death year or range
            - q.death.place: Death locality
            - q.spouse.givenName, q.spouse.surname
            - q.father.givenName, q.father.surname
            - count: Maximum number of entries (default 20)
        """
        return self._request("GET", "/platform/search/records", params=query_params)

    def search_tree(self, query_params: dict[str, Any]) -> dict[str, Any]:
        """Searches the FamilyTree database directly for candidate person profiles."""
        return self._request("GET", "/platform/tree/search", params=query_params)
