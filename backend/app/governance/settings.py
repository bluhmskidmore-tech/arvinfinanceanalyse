import os
from decimal import Decimal
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root: backend/app/governance/settings.py -> parents[3] == <repo>
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILES = (
    _REPO_ROOT / "config" / ".env",
    _REPO_ROOT / ".env",
)
DEFAULT_POSTGRES_DSN = "postgresql://moss:moss@localhost:5432/moss"
DEV_POSTGRES_DSN = "postgresql://moss:moss@127.0.0.1:55432/moss"
_DEV_POSTGRES_CLUSTER_DATA_DIR = Path("tmp-governance") / "pgdev" / "data"


def resolve_postgres_dsn(postgres_dsn: str, *, repo_root: Path = _REPO_ROOT) -> str:
    normalized = str(postgres_dsn or "").strip() or DEFAULT_POSTGRES_DSN
    if normalized != DEFAULT_POSTGRES_DSN:
        return normalized
    if (repo_root / _DEV_POSTGRES_CLUSTER_DATA_DIR).exists():
        return DEV_POSTGRES_DSN
    return normalized


def resolve_governance_sql_dsn(governance_sql_dsn: str, postgres_dsn: str) -> str:
    normalized = str(governance_sql_dsn or "").strip()
    return normalized or str(postgres_dsn).strip()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, env_prefix="MOSS_", extra="ignore")

    environment: str = "development"
    agent_enabled: bool = False
    postgres_dsn: str = DEFAULT_POSTGRES_DSN
    governance_sql_dsn: str = ""
    governance_backend: str = "jsonl"
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
    fx_official_source_path: str = ""
    fx_mid_csv_path: str = ""
    product_category_source_dir: Path = Path("data_input") / "pnl_\u603b\u8d26\u5bf9\u8d26-\u65e5\u5747"
    ftp_rate_pct: Decimal = Decimal("1.75")
    formal_pnl_enabled: bool = True
    formal_pnl_scope_json: str = '["*"]'
    cors_origins: str = (
        "http://localhost:5888,http://127.0.0.1:5888,http://[::1]:5888,"
        "http://localhost:5173,http://127.0.0.1:5173,http://[::1]:5173"
    )

    def model_post_init(self, __context) -> None:
        self.postgres_dsn = resolve_postgres_dsn(self.postgres_dsn, repo_root=_REPO_ROOT)
        self.governance_sql_dsn = resolve_governance_sql_dsn(
            self.governance_sql_dsn,
            self.postgres_dsn,
        )


def get_settings() -> Settings:
    return Settings()


def _cache_clear() -> None:
    return None


get_settings.cache_clear = _cache_clear
