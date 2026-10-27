"""Configuration management for FamilySearch Research Engine."""

from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    familysearch_session_id: str = Field(
        default="",
        alias="FAMILYSEARCH_SESSION_ID",
        description="Active FamilySearch fssessionid token from browser cookies.",
    )

    familysearch_env: Literal["production", "beta"] = Field(
        default="production",
        alias="FAMILYSEARCH_ENV",
        description="API environment: 'production' (default) or 'beta'.",
    )

    familysearch_app_key: str = Field(
        default="",
        alias="FAMILYSEARCH_APP_KEY",
        description="Optional Developer App Key (Client ID) from FamilySearch Developer Portal.",
    )

    @property
    def base_url(self) -> str:
        """Returns the appropriate API base URL."""
        if self.familysearch_env == "beta":
            return "https://apibeta.familysearch.org"
        return "https://api.familysearch.org"

    @property
    def is_configured(self) -> bool:
        """Check if session token or app key is provided."""
        return bool(self.familysearch_session_id.strip() or self.familysearch_app_key.strip())


def get_settings() -> Settings:
    """Instantiate and return settings singleton."""
    return Settings()
