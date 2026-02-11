"""Application configuration using Pydantic settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Application
    APP_NAME: str = "Corporate Intelligence Graph"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Anthropic Claude API
    ANTHROPIC_API_KEY: str = ""

    # SEC EDGAR
    SEC_EDGAR_USER_AGENT: str = "CompanyName admin@company.com"

    # Server
    PORT: int = 8000

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]


settings = Settings()
