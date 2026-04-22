import os
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

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


def resolve_repo_relative_path(path_value: str, *, repo_root: Path = _REPO_ROOT) -> str:
    normalized = str(path_value or "").strip()
    if not normalized:
        return normalized

    candidate = Path(normalized)
    if candidate.is_absolute():
        return str(candidate)

    return str((repo_root / candidate).resolve())


def _env_nonempty(key: str) -> bool:
    value = os.environ.get(key)
    return bool(value and str(value).strip())


# Default relative path for product-category PnL sources (must match field default below).
_DEFAULT_PRODUCT_CATEGORY_REL = Path("data_input") / "pnl_\u603b\u8d26\u5bf9\u8d26-\u65e5\u5747"


def resolve_data_input_root_path(*, repo_root: Path, pydantic_value: Path) -> Path:
    """
    Raw input directory (aligned with MOSS-SYSTEM-V1 `resolve_raw_dir`):

    1. ``MOSS_DATA_INPUT_ROOT`` — explicit override (via Settings field).
    2. ``RAW_FILES_DIR`` — V1 env; relative paths anchor to repo root.
    3. ``<repo>/data_warehouse/raw_files`` if that directory exists.
    4. Otherwise ``pydantic_value`` resolved relative to repo (default ``data_input``).
    """
    if _env_nonempty("MOSS_DATA_INPUT_ROOT"):
        return Path(resolve_repo_relative_path(str(pydantic_value), repo_root=repo_root)).resolve()

    raw_files_env = str(os.environ.get("RAW_FILES_DIR", "") or "").strip()
    if raw_files_env:
        candidate = Path(raw_files_env).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
        return resolved

    v1_raw = (repo_root / "data_warehouse" / "raw_files").resolve()
    if v1_raw.is_dir():
        return v1_raw

    return Path(resolve_repo_relative_path(str(pydantic_value), repo_root=repo_root)).resolve()


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
    tushare_token: str = ""
    tushare_news_src: str = "sina"
    fx_official_source_path: str = ""
    fx_mid_csv_path: str = ""
    product_category_source_dir: Path = _DEFAULT_PRODUCT_CATEGORY_REL
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
        self.duckdb_path = resolve_repo_relative_path(
            self.duckdb_path,
            repo_root=_REPO_ROOT,
        )
        self.governance_path = Path(
            resolve_repo_relative_path(
                str(self.governance_path),
                repo_root=_REPO_ROOT,
            )
        )
        self.data_input_root = resolve_data_input_root_path(
            repo_root=_REPO_ROOT,
            pydantic_value=self.data_input_root,
        )
        self.local_archive_path = Path(
            resolve_repo_relative_path(
                str(self.local_archive_path),
                repo_root=_REPO_ROOT,
            )
        )
        _default_pc_resolved = (
            Path(resolve_repo_relative_path(str(_DEFAULT_PRODUCT_CATEGORY_REL), repo_root=_REPO_ROOT)).resolve()
        )
        _pc_from_field = Path(
            resolve_repo_relative_path(str(self.product_category_source_dir), repo_root=_REPO_ROOT),
        ).resolve()
        if _pc_from_field == _default_pc_resolved:
            self.product_category_source_dir = (self.data_input_root / _DEFAULT_PRODUCT_CATEGORY_REL.name).resolve()
        else:
            self.product_category_source_dir = _pc_from_field
        self.choice_macro_catalog_file = resolve_repo_relative_path(
            self.choice_macro_catalog_file,
            repo_root=_REPO_ROOT,
        )
        self.choice_macro_commands_file = resolve_repo_relative_path(
            self.choice_macro_commands_file,
            repo_root=_REPO_ROOT,
        )
        self.choice_news_topics_file = resolve_repo_relative_path(
            self.choice_news_topics_file,
            repo_root=_REPO_ROOT,
        )
        self.fx_official_source_path = resolve_repo_relative_path(
            self.fx_official_source_path,
            repo_root=_REPO_ROOT,
        )
        self.fx_mid_csv_path = resolve_repo_relative_path(
            self.fx_mid_csv_path,
            repo_root=_REPO_ROOT,
        )


def get_settings() -> Settings:
    return Settings()


def _cache_clear() -> None:
    return None


cast(Any, get_settings).cache_clear = _cache_clear
