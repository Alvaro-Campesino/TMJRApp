from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _empty_to_none(v):
    """Convierte cadenas vacías (típico de .env con `KEY=`) en None."""
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field("dev")
    log_level: str = Field("INFO")

    database_url: str

    telegram_token: str | None = None
    telegram_webhook_url: str | None = None
    telegram_webhook_secret: str | None = None
    telegram_webhook_cert_file: str | None = None
    telegram_chat_id: str | None = None
    telegram_thread_id: int | None = None

    @field_validator(
        "telegram_token",
        "telegram_webhook_url",
        "telegram_webhook_secret",
        "telegram_webhook_cert_file",
        "telegram_chat_id",
        "telegram_thread_id",
        mode="before",
    )
    @classmethod
    def _blank_string_is_none(cls, v):
        return _empty_to_none(v)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
