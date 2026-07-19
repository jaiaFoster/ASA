from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASA_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://asa:asa@localhost:5432/asa"
    environment: str = "development"
    quote_provider: str = "deterministic_fake"
    fresh_for_seconds: int = Field(default=300, ge=1)
    cors_origins: str = "http://localhost:5173"
