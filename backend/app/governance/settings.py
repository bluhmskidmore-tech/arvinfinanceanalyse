import os
import sys
from decimal import Decimal
from pathlib import Path
from threading import RLock
from types import ModuleType
from typing import Any, Literal, cast

from pydantic import Field, PositiveFloat, PositiveInt, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root: backend/app/governance/settings.py -> parents[3] == <repo>
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILES = (
    _REPO_ROOT / "config" / ".env",
    _REPO_ROOT / ".env",
)
DEFAULT_POSTGRES_DSN = "postgresql://moss:moss@localhost:5432/moss"
DEV_POSTGRES_DSN = "postgresql://moss:moss@127.0.0.1:55432/moss"
# Default interpreter used inside the Hermes WSL distro; override via
# MOSS_AGENT_HERMES_PYTHON_PATH without changing existing deployments.
DEFAULT_AGENT_HERMES_PYTHON_PATH = "/home/hermes/hermes-agent/venv/bin/python"
DEFAULT_AGENT_PI_COMMAND = "pi.cmd" if sys.platform == "win32" else "pi"
_DEV_POSTGRES_CLUSTER_DATA_DIR = Path("tmp-governance") / "pgdev" / "data"
_SETTINGS_CACHE_STATE_MODULE = "backend.app.governance._settings_cache_state"
_settings_cache_state_module = sys.modules.setdefault(
    _SETTINGS_CACHE_STATE_MODULE,
    ModuleType(_SETTINGS_CACHE_STATE_MODULE),
)
_settings_cache_state = vars(_settings_cache_state_module)
_settings_cache_state.setdefault("lock", RLock())
_settings_cache_state.setdefault("generation", 0)
_settings_cache_state.pop("settings", None)


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


def resolve_data_input_root_path(
    *,
    repo_root: Path,
    pydantic_value: Path,
    explicit: bool | None = None,
) -> Path:
    """
    Raw input directory (aligned with MOSS-SYSTEM-V1 `resolve_raw_dir`):

    1. ``MOSS_DATA_INPUT_ROOT`` — explicit override (via Settings field).
       Settings passes ``explicit`` from ``model_fields_set`` so values from
       ``.env`` files or constructor args rank the same as process env vars;
       when ``explicit`` is None, only ``os.environ`` is checked.
    2. ``RAW_FILES_DIR`` — V1 env; relative paths anchor to repo root.
    3. ``<repo>/data_warehouse/raw_files`` if that directory exists.
    4. Otherwise ``pydantic_value`` resolved relative to repo (default ``data_input``).
    """
    is_explicit = _env_nonempty("MOSS_DATA_INPUT_ROOT") if explicit is None else explicit
    if is_explicit:
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
    _data_input_root_explicit: bool = PrivateAttr(default=False)

    environment: Literal["development", "production", "staging", "test"] = "development"
    # Native single-user entrypoints opt in; container/gateway development keeps
    # its existing network contract unless this policy is explicitly selected.
    local_only_api: bool = False
    agent_enabled: bool = False
    agent_dev_scope_bypass: bool = False
    agent_provider: Literal["local", "hermes", "dexter", "pi"] = "local"
    agent_hermes_command: str = "wsl.exe"
    agent_hermes_wsl_distro: str = "HermesUbuntu"
    agent_hermes_home: str = ""
    agent_hermes_transport: Literal["cli", "bridge"] = "cli"
    agent_hermes_bridge_url: str = "http://127.0.0.1:7891"
    agent_hermes_model: str = ""
    agent_hermes_toolsets: str = ""
    agent_hermes_max_turns: PositiveInt = 20
    agent_hermes_timeout_seconds: PositiveFloat = 180.0
    agent_hermes_python_path: str = DEFAULT_AGENT_HERMES_PYTHON_PATH
    agent_dexter_command: str = "dexter"
    agent_dexter_transport: Literal["cli", "sidecar"] = "cli"
    agent_dexter_bridge_url: str = "http://127.0.0.1:7892"
    agent_dexter_model: str = ""
    agent_dexter_toolsets: str = ""
    agent_dexter_timeout_seconds: PositiveFloat = 180.0
    # Pi defaults to a local RPC binary with all Pi-side tools disabled.  The
    # Jev gate is separately opt-in so adding this provider cannot open an
    # external decision call in existing deployments.
    agent_pi_command: str = DEFAULT_AGENT_PI_COMMAND
    agent_pi_model: str = ""
    agent_pi_max_turns: PositiveInt = 1
    agent_pi_timeout_seconds: PositiveFloat = 120.0
    # Explicit local opt-in: only the parent process OPENAI_API_KEY may be
    # forwarded to the Pi subprocess; it is never persisted by MOSS.
    agent_pi_forward_api_key: bool = False
    agent_jev_mode: Literal["off", "shadow", "active"] = "off"
    agent_jev_api_url: str = "https://api.typesafe.ai/v1/systemone"
    agent_jev_model: str = "jev-latest"
    agent_jev_timeout_seconds: PositiveFloat = 2.0
    agent_jev_min_confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    # queued 状态的 run 超过该秒数未被执行时，读取状态会收敛为 failed
    # （error_type=StaleQueuedAgentRun）。缺省 600 与
    # agent_run_service.AGENT_RUN_QUEUED_STALE_SECONDS 保持一致。
    agent_run_queued_timeout_seconds: PositiveFloat = 600.0
    agent_run_stream_retention_days: PositiveFloat = 7.0
    # suggested action 确认 token 的 HMAC secret。多进程部署（API 进程 +
    # worker 进程）必须显式配置同一值，否则跨进程签发/校验会失败；
    # 为空时回退进程本地随机 secret（仅单进程可用）。
    agent_action_token_secret: str = ""
    postgres_dsn: str = DEFAULT_POSTGRES_DSN
    governance_sql_dsn: str = ""
    governance_backend: Literal["jsonl", "sql-authority"] = "jsonl"
    source_preview_governance_backend: Literal["jsonl", "sql-authority", "sql-shadow"] = "jsonl"
    job_state_dsn: str = ""
    redis_dsn: str = "redis://localhost:6379/0"
    duckdb_path: str = "data/moss.duckdb"
    financial_publication_enabled: bool = False
    financial_publication_root: str = ""
    system_read_publication_enabled: bool = False
    balance_analysis_publication_enabled: bool = False
    balance_analysis_publication_root: str = ""
    governance_path: Path = Path("data/governance")
    data_input_root: Path = Path("data_input")
    object_store_mode: Literal["local", "minio"] = "local"
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
    choice_stock_catalog_file: str = "config/choice_stock_catalog.json"
    choice_macro_commands_file: str = ""
    choice_news_topics_file: str = "config/choice_news_topics.json"
    choice_timeout_seconds: PositiveFloat = 10.0
    tushare_token: str = ""
    tushare_news_src: str = "sina"
    fx_official_source_path: str = ""
    fx_mid_csv_path: str = ""
    product_category_source_dir: Path = _DEFAULT_PRODUCT_CATEGORY_REL
    ftp_rate_pct: Decimal = Decimal("1.75")
    #: Provenance-only override for the frozen formal financial indicator workbook
    #: reference; empty means the contract module default (repo-relative) is used.
    #: The value is metadata and never participates in IO.
    formal_financial_indicators_workbook: str = ""
    formal_pnl_enabled: bool = True
    formal_pnl_scope_json: str = '["*"]'
    #: 为 True 时，/api/pnl/by-business-ytd 优先用 fact_formal_pnl_fi + fact_nonstd_pnl_bridge 按年累计聚合（与物化正式口径一致）；为 False 时沿用刷新包 + V1 兼容变换（供契约测试与排障）。
    pnl_by_business_ytd_prefer_formal_facts: bool = True
    home_snapshot_prewarm_enabled: bool = True
    home_income_trend_prewarm_enabled: bool = True
    market_home_prewarm_enabled: bool = True
    cors_origins: str = (
        "http://localhost:5888,http://127.0.0.1:5888,http://[::1]:5888,"
        "http://localhost:5173,http://127.0.0.1:5173,http://[::1]:5173"
    )

    def model_post_init(self, __context) -> None:
        explicit_fields = set(getattr(self, "model_fields_set", set()))
        self._data_input_root_explicit = "data_input_root" in explicit_fields or _env_nonempty("RAW_FILES_DIR")
        self.governance_backend = cast(
            Literal["jsonl", "sql-authority"],
            _resolve_production_governance_backend(
                self.governance_backend,
                environment=self.environment,
                field_name="governance_backend",
                explicit="governance_backend" in explicit_fields,
            ),
        )
        self.source_preview_governance_backend = cast(
            Literal["jsonl", "sql-authority", "sql-shadow"],
            _resolve_production_governance_backend(
                self.source_preview_governance_backend,
                environment=self.environment,
                field_name="source_preview_governance_backend",
                explicit="source_preview_governance_backend" in explicit_fields,
            ),
        )
        self.postgres_dsn = resolve_postgres_dsn(self.postgres_dsn, repo_root=_REPO_ROOT)
        self.governance_sql_dsn = resolve_governance_sql_dsn(
            self.governance_sql_dsn,
            self.postgres_dsn,
        )
        self.duckdb_path = resolve_repo_relative_path(
            self.duckdb_path,
            repo_root=_REPO_ROOT,
        )
        self.financial_publication_root = self.financial_publication_root.strip()
        if self.system_read_publication_enabled and not self.financial_publication_root:
            raise ValueError(
                "financial_publication_root is required when system read publication is enabled."
            )
        if self.financial_publication_enabled and not self.financial_publication_root:
            raise ValueError("financial_publication_root is required when financial publication is enabled.")
        if self.financial_publication_root:
            self.financial_publication_root = resolve_repo_relative_path(
                self.financial_publication_root,
                repo_root=_REPO_ROOT,
            )
        self.balance_analysis_publication_root = self.balance_analysis_publication_root.strip()
        if self.balance_analysis_publication_enabled and not self.balance_analysis_publication_root:
            raise ValueError(
                "balance_analysis_publication_root is required when balance-analysis publication is enabled."
            )
        if self.balance_analysis_publication_root:
            self.balance_analysis_publication_root = resolve_repo_relative_path(
                self.balance_analysis_publication_root,
                repo_root=_REPO_ROOT,
            )
        if (
            self.balance_analysis_publication_root
            and self.financial_publication_root
            and Path(self.balance_analysis_publication_root).resolve()
            == Path(self.financial_publication_root).resolve()
        ):
            raise ValueError(
                "balance_analysis_publication_root must be separate from financial_publication_root."
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
            explicit="data_input_root" in explicit_fields,
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
        self.choice_stock_catalog_file = resolve_repo_relative_path(
            self.choice_stock_catalog_file,
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


def _resolve_production_governance_backend(
    backend: str,
    *,
    environment: str,
    field_name: str,
    explicit: bool,
) -> str:
    normalized = str(backend or "").strip()
    if str(environment or "").strip().lower() != "production":
        return normalized
    if normalized == "jsonl":
        if explicit:
            raise ValueError(f"production {field_name} cannot use jsonl authority")
        return "sql-authority"
    return normalized or "sql-authority"


_settings_cache_generation = -1
_settings_cache_value: Settings | None = None


def get_settings() -> Settings:
    global _settings_cache_generation, _settings_cache_value

    with _settings_cache_state["lock"]:
        generation = _settings_cache_state["generation"]
        if _settings_cache_value is None or _settings_cache_generation != generation:
            _settings_cache_value = Settings()
            _settings_cache_generation = generation
        return _settings_cache_value


def _cache_clear() -> None:
    with _settings_cache_state["lock"]:
        _settings_cache_state["generation"] += 1


cast(Any, get_settings).cache_clear = _cache_clear
