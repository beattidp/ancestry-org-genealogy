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
        headers = dict(self.session_manager.get_auth_headers())

        if not headers:
            raise FamilySearchAuthError(
                "Authentication headers are missing. Provide a valid FAMILYSEARCH_SESSION_ID in .env."
            )

        if json_data is not None and "Content-Type" not in headers:
            headers["Content-Type"] = "application/x-gedcomx-v1+json"

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

            if response.status_code == 201:
                result: dict[str, Any] = {}
                if response.content:
                    try:
                        result = response.json()
                    except Exception:
                        pass
                if "Location" in response.headers:
                    result["location"] = response.headers["Location"]
                if "X-Entity-ID" in response.headers:
                    result["id"] = response.headers["X-Entity-ID"]
                return result

            if response.status_code == 204:
                return {}

            if response.status_code in (401, 403):
                tree_write_hint = ""
                if response.status_code == 403 and method.upper() in ("POST", "PUT", "DELETE"):
                    tree_write_hint = (
                        " Write permission denied: Mutating FamilySearch Tree records requires "
                        "an approved developer account with 'Tree Write' permissions or certified app status."
                    )
                raise FamilySearchAuthError(
                    f"Authentication failed ({response.status_code}): Session token is invalid, expired, or lacks write permissions.{tree_write_hint} "
                    "Please verify your credentials in .env.",
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

    # -------------------------------------------------------------------------
    # Tree Write Endpoints (Selective Updates & Evidence Rationales)
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_change_message(change_message: str | None) -> str:
        """Enforces FamilySearch requirement for human-readable change justification."""
        if not change_message or not change_message.strip():
            raise ValueError(
                "A non-empty changeMessage justification is strictly required for FamilySearch write operations."
            )
        return change_message.strip()

    def add_or_update_person_fact(
        self,
        pid: str,
        fact_type: str,
        date_original: str | None = None,
        place_original: str | None = None,
        change_message: str = "",
        formal_date: str | None = None,
        place_coordinates: tuple[float, float] | None = None,
    ) -> dict[str, Any]:
        """Updates or appends a vital or personal fact for a Person profile.

        Endpoint: POST /platform/tree/persons/{pid}
        GEDCOM X Payload: Person with facts and attribution.changeMessage.

        Args:
            pid: Person ID (e.g. '9ZMG-JSD').
            fact_type: GEDCOM X URI (e.g. 'http://gedcomx.org/Birth') or short name ('Birth').
            date_original: Recorded natural date string (e.g. 'about 1605', '1888-03-09').
            place_original: Recorded place name string (e.g. 'Liberton, Midlothian, Scotland').
            change_message: Mandatory human-readable justification note.
            formal_date: Optional ISO 8601 / GEDCOM date (e.g. '+1888-03-09').
            place_coordinates: Optional tuple of (latitude, longitude) for geospatial place reference.
        """
        valid_message = self._validate_change_message(change_message)
        uri_type = fact_type if fact_type.startswith("http") else f"http://gedcomx.org/{fact_type}"

        fact: dict[str, Any] = {
            "type": uri_type,
            "attribution": {"changeMessage": valid_message},
        }

        if date_original or formal_date:
            date_obj: dict[str, Any] = {}
            if date_original:
                date_obj["original"] = date_original
            if formal_date:
                date_obj["formal"] = formal_date
            fact["date"] = date_obj

        if place_original:
            place_obj: dict[str, Any] = {"original": place_original}
            if place_coordinates:
                place_obj["description"] = "#place-ref"
            fact["place"] = place_obj

        person_entry: dict[str, Any] = {
            "id": pid,
            "facts": [fact],
            "attribution": {"changeMessage": valid_message},
        }

        payload: dict[str, Any] = {"persons": [person_entry]}

        if place_coordinates and place_original:
            lat, lon = place_coordinates
            payload["places"] = [
                {
                    "id": "place-ref",
                    "names": [{"value": place_original}],
                    "latitude": lat,
                    "longitude": lon,
                }
            ]

        return self._request("POST", f"/platform/tree/persons/{pid}", json_data=payload)

    def create_source_description(
        self,
        about_url: str,
        title: str,
        citation_text: str,
        change_message: str,
    ) -> dict[str, Any]:
        """Creates a top-level SourceDescription in FamilySearch.

        Endpoint: POST /platform/sources/descriptions
        GEDCOM X Payload: sourceDescriptions list with titles, citations, and attribution.
        """
        valid_message = self._validate_change_message(change_message)
        payload = {
            "sourceDescriptions": [
                {
                    "about": about_url,
                    "titles": [{"value": title}],
                    "citations": [{"value": citation_text}],
                    "attribution": {"changeMessage": valid_message},
                }
            ]
        }
        return self._request("POST", "/platform/sources/descriptions", json_data=payload)

    def attach_person_source(
        self,
        pid: str,
        source_description_url: str,
        change_message: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Attaches a SourceDescription reference to a Person profile.

        Endpoint: POST /platform/tree/persons/{pid}
        GEDCOM X Payload: persons list containing sources references.
        """
        valid_message = self._validate_change_message(change_message)
        source_ref: dict[str, Any] = {
            "description": source_description_url,
            "attribution": {"changeMessage": valid_message},
        }
        if tags:
            source_ref["tags"] = [{"value": tag} for tag in tags]

        payload = {
            "persons": [
                {
                    "id": pid,
                    "sources": [source_ref],
                }
            ]
        }
        return self._request("POST", f"/platform/tree/persons/{pid}", json_data=payload)

    def add_person_source_citation(
        self,
        pid: str,
        url: str,
        title: str,
        citation: str,
        change_message: str,
    ) -> dict[str, Any]:
        """Creates a source description and links it to a person in a combined workflow."""
        valid_message = self._validate_change_message(change_message)
        source_res = self.create_source_description(
            about_url=url,
            title=title,
            citation_text=citation,
            change_message=valid_message,
        )
        source_url = source_res.get("location") or (
            f"{self.base_url}/platform/tree/sources/{source_res['id']}" if "id" in source_res else url
        )
        return self.attach_person_source(pid, source_url, valid_message)

    def create_relationship(
        self,
        rel_type: str,
        person1_pid: str,
        person2_pid: str,
        change_message: str,
    ) -> dict[str, Any]:
        """Creates a parent-child or couple relationship between two persons.

        Endpoint: POST /platform/tree/relationships
        Supported types: 'ParentChild', 'Couple', or full GEDCOM X URIs.
        """
        valid_message = self._validate_change_message(change_message)
        uri_type = rel_type if rel_type.startswith("http") else f"http://gedcomx.org/{rel_type}"

        payload = {
            "relationships": [
                {
                    "type": uri_type,
                    "person1": {"resource": f"#{person1_pid}", "resourceId": person1_pid},
                    "person2": {"resource": f"#{person2_pid}", "resourceId": person2_pid},
                    "attribution": {"changeMessage": valid_message},
                }
            ]
        }
        return self._request("POST", "/platform/tree/relationships", json_data=payload)

    def check_person_matches(self, query_params: dict[str, Any]) -> list[dict[str, Any]]:
        """Queries duplicate detection endpoint for matches before creating a person profile.

        Endpoint: GET /platform/tree/matches
        """
        res = self._request("GET", "/platform/tree/matches", params=query_params)
        entries = res.get("entries", [])
        if entries:
            return entries
        return res.get("persons", [])

    def create_person(
        self,
        person_payload: dict[str, Any],
        change_message: str,
        check_duplicates: bool = True,
    ) -> dict[str, Any]:
        """Creates a new person profile on FamilyTree.

        Endpoint: POST /platform/tree/persons
        Enforces duplicate detection check before creation if check_duplicates=True.
        """
        valid_message = self._validate_change_message(change_message)

        if check_duplicates:
            given_name = ""
            surname = ""
            persons = person_payload.get("persons", [])
            if persons:
                names = persons[0].get("names", [])
                if names and "nameForms" in names[0]:
                    parts = names[0]["nameForms"][0].get("parts", [])
                    for part in parts:
                        ptype = part.get("type", "")
                        if "Given" in ptype:
                            given_name = part.get("value", "")
                        elif "Surname" in ptype:
                            surname = part.get("value", "")

            if given_name or surname:
                match_params = {"q.givenName": given_name, "q.surname": surname}
                matches = self.check_person_matches(match_params)
                if matches:
                    raise ValueError(
                        f"Potential duplicate matches found ({len(matches)} candidates). "
                        "Review matches via check_person_matches() or set check_duplicates=False to override."
                    )

        if "persons" in person_payload and person_payload["persons"]:
            person_payload["persons"][0]["attribution"] = {"changeMessage": valid_message}

        return self._request("POST", "/platform/tree/persons", json_data=person_payload)

