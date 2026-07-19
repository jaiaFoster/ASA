from hashlib import sha256
from json import dumps

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ASA_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(
        default="postgresql+psycopg://asa:asa@localhost:5432/asa",
        validation_alias=AliasChoices("DATABASE_URL", "ASA_DATABASE_URL"),
    )
    environment: str = "development"
    quote_provider: str = "deterministic_fake"
    broker_portfolio_provider: str = "deterministic_fake_broker"
    robinhood_username: SecretStr | None = None
    robinhood_password: SecretStr | None = None
    robinhood_totp_secret: SecretStr | None = None
    robinhood_account_numbers: str | None = None
    fresh_for_seconds: int = Field(default=300, ge=1)
    portfolio_fresh_for_seconds: int = Field(default=3600, ge=1)
    cors_origins: str = "http://localhost:5173"
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("PORT", "ASA_PORT"),
    )

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @model_validator(mode="after")
    def validate_selected_broker(self) -> "Settings":
        if self.broker_portfolio_provider == "robinhood" and (
            self.robinhood_username is None or self.robinhood_password is None
        ):
            raise ValueError("Robinhood provider requires username and password")
        return self

    @property
    def selected_robinhood_accounts(self) -> tuple[str, ...]:
        if not self.robinhood_account_numbers:
            return ()
        return tuple(
            account.strip()
            for account in self.robinhood_account_numbers.split(",")
            if account.strip()
        )

    def effective_configuration_hash(self) -> str:
        safe_values = {
            "environment": self.environment,
            "quote_provider": self.quote_provider,
            "broker_portfolio_provider": self.broker_portfolio_provider,
            "fresh_for_seconds": self.fresh_for_seconds,
            "portfolio_fresh_for_seconds": self.portfolio_fresh_for_seconds,
        }
        return sha256(dumps(safe_values, sort_keys=True).encode()).hexdigest()
