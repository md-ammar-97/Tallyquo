from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Loaded from environment / .env — never hardcoded.

    Two DSNs by design (ADR-001): `database_url` is the low-privilege
    `tallyquo_app` role used by the running API (no BYPASSRLS, RLS applies).
    `database_admin_url` is used only by Alembic to create roles, enable RLS,
    and define policies — operations an app-role connection must never be
    able to perform.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: str = "local"

    # Comma-separated in the env file; the Vite dev server default is here
    # so local dev works out of the box.
    allowed_origins: str = "http://localhost:5173"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    database_url: str = (
        "postgresql+asyncpg://tallyquo_app:tallyquo_app@localhost:5435/tallyquo"
    )
    database_admin_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5435/tallyquo"
    )

    # Supabase Storage's S3-compatible endpoint. Empty in local dev until a
    # project exists; storage.py raises a clear error rather than silently
    # no-op-ing if code tries to use it unconfigured.
    storage_endpoint_url: str = ""
    storage_region: str = "us-east-1"
    storage_access_key_id: str = ""
    storage_secret_access_key: str = ""
    storage_bucket: str = "tallyquo"
    signed_url_ttl_seconds: int = 300

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
