from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore[attr-defined]
import os

# PUBLIC_INTERFACE
class AppSettings(BaseSettings):
    """Application settings loaded from environment variables with sane defaults."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # App
    APP_NAME: str = Field(default="MCP Server", description="Human-friendly application name")
    ENV: str = Field(default="development", description="Environment name: development|staging|production")
    DEBUG: bool = Field(default=True, description="Enable debug mode")
    PORT: int = Field(default=3001, description="Port the FastAPI app will bind to (preserve preview port handling)")

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins. Comma-separated list in env.",
    )

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/mcp_db",
        description="SQLAlchemy database URL",
    )

    # Auth / JWT
    JWT_SECRET_KEY: str = Field(default="change-me", description="Secret key for signing JWT tokens")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT access token expiry in minutes")

    # JIRA
    JIRA_BASE_URL: Optional[str] = Field(default=None, description="Base URL for JIRA instance, e.g., https://your-domain.atlassian.net")
    JIRA_EMAIL: Optional[str] = Field(default=None, description="JIRA user/email for API access")
    JIRA_API_TOKEN: Optional[str] = Field(default=None, description="JIRA API token")
    JIRA_PROJECT_KEY: Optional[str] = Field(default=None, description="Default JIRA Project Key")
    JIRA_WEBHOOK_SECRET: Optional[str] = Field(default=None, description="Shared secret to validate inbound JIRA webhooks")

    # Misc
    REQUEST_TIMEOUT_SECONDS: int = Field(default=30, description="Default outbound HTTP request timeout in seconds")

    def cors_origins_list(self) -> List[str]:
        """Return parsed list of CORS origins from BACKEND_CORS_ORIGINS env."""
        if isinstance(self.BACKEND_CORS_ORIGINS, list):
            return self.BACKEND_CORS_ORIGINS
        value = os.getenv("BACKEND_CORS_ORIGINS", "")
        if not value:
            return ["*"]
        return [origin.strip() for origin in value.split(",") if origin.strip()]

# PUBLIC_INTERFACE
@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Get cached application settings instance."""
    return AppSettings()
