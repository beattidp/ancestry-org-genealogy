"""Authentication and session management for FamilySearch Platform API."""

from dataclasses import dataclass
from typing import Any
import httpx

from src.config import Settings, get_settings


@dataclass
class AuthStatus:
    """Represents the outcome of a session validation probe."""

    is_valid: bool
    status_code: int
    message: str
    user_id: str | None = None
    display_name: str | None = None
    contact_name: str | None = None
    person_id: str | None = None
    raw_user: dict[str, Any] | None = None


class SessionManager:
    """Manages FamilySearch credentials, token headers, and session verification."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def token(self) -> str:
        """Returns the active session token."""
        return self.settings.familysearch_session_id.strip()

    def get_auth_headers(self) -> dict[str, str]:
        """Constructs headers required for FamilySearch platform requests."""
        if not self.token:
            return {}

        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/x-gedcomx-v1+json, application/json",
            "User-Agent": "FamilySearchResearchEngine/1.0",
        }

    def validate_session(self) -> AuthStatus:
        """Probes the FamilySearch identity endpoint to verify the active session."""
        if not self.token:
            return AuthStatus(
                is_valid=False,
                status_code=0,
                message=(
                    "No FAMILYSEARCH_SESSION_ID configured. "
                    "Copy .env.example to .env and add your fssessionid token."
                ),
            )

        url = f"{self.settings.base_url}/platform/users/current"
        headers = self.get_auth_headers()

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                users = data.get("users", [])
                user_info = users[0] if users else {}

                user_id = user_info.get("id")
                display_name = user_info.get("displayName") or user_info.get("contactName")
                contact_name = user_info.get("contactName")
                person_id = user_info.get("personId") or user_info.get("treeUserId")

                return AuthStatus(
                    is_valid=True,
                    status_code=200,
                    message="Session token is valid and active.",
                    user_id=user_id,
                    display_name=display_name,
                    contact_name=contact_name,
                    person_id=person_id,
                    raw_user=user_info,
                )

            elif response.status_code in (401, 403):
                return AuthStatus(
                    is_valid=False,
                    status_code=response.status_code,
                    message=(
                        f"Authentication failed ({response.status_code}). "
                        "The session token has expired or is invalid. "
                        "Please refresh https://familysearch.org in your browser, "
                        "copy the latest 'fssessionid' cookie, and update your .env file."
                    ),
                )
            else:
                return AuthStatus(
                    is_valid=False,
                    status_code=response.status_code,
                    message=f"Unexpected response from FamilySearch API: {response.status_code} - {response.text[:200]}",
                )

        except httpx.RequestError as exc:
            return AuthStatus(
                is_valid=False,
                status_code=0,
                message=f"Network error communicating with FamilySearch ({url}): {exc}",
            )
