from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MOSS_", extra="ignore")

    environment: str = "development"
    postgres_dsn: str = "postgresql://moss:moss@localhost:5432/moss"
    redis_dsn: str = "redis://localhost:6379/0"
    duckdb_path: str = "data/moss.duckdb"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "moss-artifacts"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
