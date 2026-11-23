"""Application settings, read from the .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "dev-only-secret-change-me-in-the-env-file-0123456789"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/triage_db"
    secret_key: str = DEFAULT_SECRET
    token_minutes: int = 60

    # Security (Sprint 5)
    environment: str = "development"        # set to "production" on a real server
    login_max_attempts: int = 5             # failed sign-ins before the account is locked
    login_lock_minutes: int = 15            # how long the lock lasts
    retention_days: int = 730               # how long consultation records are kept (an organisational policy decision)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def using_default_secret(self) -> bool:
        return self.secret_key == DEFAULT_SECRET or len(self.secret_key) < 32


settings = Settings()
