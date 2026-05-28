from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = "dev-secret-key"
    database_url: str = "sqlite+aiosqlite:///./tasks.db"

    # Rate limiting (R1)
    rate_limit_read: str = "30/minute"
    rate_limit_write: str = "10/minute"
    rate_limit_enabled: bool = True


settings = Settings()
