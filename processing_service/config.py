from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    encryption_master_key: str  # base64-encoded 32-byte key for envelope encryption
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"
    port: int = 8002


@lru_cache
def get_settings() -> Settings:
    return Settings()
