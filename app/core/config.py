from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    rabbitmq_url: str
    api_key: str

    outbox_poll_interval: float = 2.0
    outbox_batch_size: int = 50
    outbox_max_attempts: int = 5

    webhook_max_attempts: int = 3
    webhook_backoff_base: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
