from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root: backend/app/governance/settings.py -> parents[3] == <repo>
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILES = (
    _REPO_ROOT / "config" / ".env",
    _REPO_ROOT / ".env",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, env_prefix="MOSS_", extra="ignore")

    environment: str = "development"
    postgres_dsn: str = "postgresql://moss:moss@localhost:5432/moss"
    governance_sql_dsn: str = ""
    source_preview_governance_backend: str = "jsonl"
    job_state_dsn: str = ""
    redis_dsn: str = "redis://localhost:6379/0"
    duckdb_path: str = "data/moss.duckdb"
    governance_path: Path = Path("data/governance")
    data_input_root: Path = Path("data_input")
    object_store_mode: str = "local"
    local_archive_path: Path = Path("data/archive")
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "moss-artifacts"
    choice_macro_url: str = ""
    choice_username: str = ""
    choice_password: str = ""
    choice_emquant_parent: str = ""
    choice_start_options: str = ""
    choice_request_options: str = ""
    choice_macro_series_json: str = "[]"
    choice_macro_catalog_file: str = "config/choice_macro_catalog.json"
    choice_macro_commands_file: str = ""
    choice_news_topics_file: str = "config/choice_news_topics.json"
    choice_timeout_seconds: float = 10.0
    product_category_source_dir: Path = Path("data_input") / "pnl_\u603b\u8d26\u5bf9\u8d26-\u65e5\u5747"
    ftp_rate_pct: Decimal = Decimal("1.75")
    formal_pnl_enabled: bool = False
    formal_pnl_scope_json: str = "[]"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
