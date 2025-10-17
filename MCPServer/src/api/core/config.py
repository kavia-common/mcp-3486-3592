from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Use DB_DSN if provided, otherwise discrete DB_* variables.
    """

    APP_NAME: str = Field(default="MCP Server", description="Application name")
    APP_VERSION: str = Field(default="0.1.0", description="Application version")
    APP_DESCRIPTION: str = Field(
        default="MCP Server provides message processing and JIRA integration.",
        description="Application description",
    )

    # Database
    DB_DSN: str | None = Field(default=None, description="Database DSN (asyncpg).")
    DB_HOST: str = Field(default="localhost", description="DB host")
    DB_PORT: int = Field(default=5432, description="DB port")
    DB_USER: str = Field(default="postgres", description="DB user")
    DB_PASSWORD: str = Field(default="postgres", description="DB password")
    DB_NAME: str = Field(default="mcp_db", description="DB name")

    # Security
    JWT_SECRET_KEY: str = Field(default="change-me", description="JWT secret")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, description="JWT TTL minutes")

    # CORS
    CORS_ALLOW_ORIGINS: str = Field(default="*", description="Comma-separated origins")

    # JIRA
    JIRA_BASE_URL: str | None = Field(default=None, description="JIRA base URL")
    JIRA_EMAIL: str | None = Field(default=None, description="JIRA account email")
    JIRA_API_TOKEN: str | None = Field(default=None, description="JIRA API token")
    JIRA_CLOUD: bool = Field(default=True, description="JIRA Cloud (True) or Server")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # PUBLIC_INTERFACE
    def database_dsn(self) -> str:
        """Compose asyncpg DSN if DB_DSN not explicitly provided."""
        if self.DB_DSN:
            return self.DB_DSN
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


@lru_cache
# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
