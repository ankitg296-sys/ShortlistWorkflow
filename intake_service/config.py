from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str  # for Supabase Storage uploads
    processing_service_url: str = "http://localhost:8002"
    internal_auth_token: str  # shared secret for service-to-service calls
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"
    port: int = 8001


@lru_cache
def get_settings() -> Settings:
    return Settings()
