from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTIVE_SERVICE = ROOT / "backend" / "app" / "services" / "executive_service.py"
PNL_BRIDGE_SERVICE = ROOT / "backend" / "app" / "services" / "pnl_bridge_service.py"
ACCOUNTING_MOVEMENT_SERVICE = (
    ROOT / "backend" / "app" / "services" / "accounting_asset_movement_service.py"
)
CFFEX_MEMBER_RANK_SERVICE = ROOT / "backend" / "app" / "services" / "cffex_member_rank_service.py"
TUSHARE_NEWS_INGEST_SERVICE = ROOT / "backend" / "app" / "services" / "tushare_news_ingest_service.py"
PNL_SERVICE = ROOT / "backend" / "app" / "services" / "pnl_service.py"
PNL_MATERIALIZE_TASK = ROOT / "backend" / "app" / "tasks" / "pnl_materialize.py"
ADB_ANALYSIS_ROUTE = ROOT / "backend" / "app" / "api" / "routes" / "adb_analysis.py"
EXTERNAL_DATA_ROUTE = ROOT / "backend" / "app" / "api" / "routes" / "external_data.py"
MACRO_TOOLKIT_ROUTE = ROOT / "backend" / "app" / "api" / "routes" / "macro_toolkit.py"
MARKET_DATA_LIVERMORE_ROUTE = ROOT / "backend" / "app" / "api" / "routes" / "market_data_livermore.py"
CHOICE_NEWS_ROUTE = ROOT / "backend" / "app" / "api" / "routes" / "choice_news.py"
HEALTH_ROUTE = ROOT / "backend" / "app" / "api" / "routes" / "health.py"
MACRO_VENDOR_ROUTE = ROOT / "backend" / "app" / "api" / "routes" / "macro_vendor.py"
API_DIR = ROOT / "backend" / "app" / "api"
SERVICES_DIR = ROOT / "backend" / "app" / "services"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _function_source(path: Path, function_name: str) -> str:
    text = _read_source(path)
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            lines = text.splitlines()
            assert node.end_lineno is not None
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"Missing function {function_name} in {path}")


def _python_sources_under(*roots: Path) -> list[Path]:
    return sorted(path for root in roots for path in root.rglob("*.py") if path.is_file())


def _repository_replace_writer_calls(text: str) -> list[str]:
    tree = ast.parse(text)
    calls: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr.startswith("replace_"):
            calls.append(node.func.attr)
        elif isinstance(node.func, ast.Name) and node.func.id.startswith("replace_"):
            calls.append(node.func.id)
    return sorted(set(calls))


def _route_duckdb_references(text: str) -> list[str]:
    tree = ast.parse(text)
    references: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            if "duckdb" in names:
                references.append("duckdb.import")
        if isinstance(node, ast.ImportFrom):
            if node.module == "duckdb":
                references.append("duckdb.import")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "duckdb":
                references.append(f"duckdb.{node.func.attr}")
        if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Attribute):
            if isinstance(node.type.value, ast.Name) and node.type.value.id == "duckdb":
                references.append("duckdb.exception")
    return sorted(set(references))


def _assert_service_avoids_direct_storage_and_formal_sql(path: Path, text: str) -> None:
    """High-risk services must orchestrate via repositories, not duckdb.connect or embedded formal SQL."""
    assert path.is_file(), f"Missing service module: {path}"

    assert "duckdb.connect(" not in text, (
        f"{path.name}: must not call duckdb.connect; use repositories for storage access."
    )

    violations: list[str] = []
    # Block SQL-shaped references to formal fact tables (direct queries / DML).
    for pattern, kind in (
        (r"\bfrom\s+[`'\"]?(fact_formal_\w+)", "FROM fact_formal_*"),
        (r"\bjoin\s+[`'\"]?(fact_formal_\w+)", "JOIN fact_formal_*"),
        (r"\binto\s+[`'\"]?(fact_formal_\w+)", "INTO fact_formal_*"),
        (r"\bupdate\s+[`'\"]?(fact_formal_\w+)", "UPDATE fact_formal_*"),
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match is not None:
            violations.append(f"{kind}: {match.group(0)!r}")

    assert not violations, (
        f"{path.name}: must not embed SQL against fact_formal_* tables:\n"
        + "\n".join(violations)
    )


def test_executive_service_avoids_storage_bypass():
    text = _read_source(EXECUTIVE_SERVICE)
    _assert_service_avoids_direct_storage_and_formal_sql(EXECUTIVE_SERVICE, text)


def test_pnl_bridge_service_avoids_storage_bypass():
    text = _read_source(PNL_BRIDGE_SERVICE)
    _assert_service_avoids_direct_storage_and_formal_sql(PNL_BRIDGE_SERVICE, text)


def test_accounting_asset_movement_service_avoids_writable_duckdb_and_low_level_materializer():
    text = _read_source(ACCOUNTING_MOVEMENT_SERVICE)
    assert ACCOUNTING_MOVEMENT_SERVICE.is_file()
    assert "duckdb.connect(str(duckdb_file), read_only=False)" not in text
    assert "duckdb.connect(duckdb_path, read_only=False)" not in text
    assert "materialize_accounting_asset_movement_on_connection" not in text
    assert ".fn(" not in text


def test_cffex_member_rank_service_delegates_storage_writes_to_tasks():
    text = _read_source(CFFEX_MEMBER_RANK_SERVICE)
    assert CFFEX_MEMBER_RANK_SERVICE.is_file()
    assert "duckdb.connect(" not in text
    assert "ensure_cffex_member_rank_schema" not in text
    assert "replace_member_rank_rows" not in text


def test_tushare_news_ingest_service_delegates_storage_writes_to_tasks():
    text = _read_source(TUSHARE_NEWS_INGEST_SERVICE)
    assert TUSHARE_NEWS_INGEST_SERVICE.is_file()
    assert "duckdb.connect(" not in text
    assert "ensure_choice_news_event_schema" not in text
    assert "purge_expired_news_events" not in text


def test_pnl_service_delegates_precompute_writes_to_tasks():
    text = _read_source(PNL_SERVICE)
    task_text = _read_source(PNL_MATERIALIZE_TASK)
    assert PNL_SERVICE.is_file()
    assert PNL_MATERIALIZE_TASK.is_file()
    assert ".replace_pnl_by_business_precompute(" not in text
    assert "persist_pnl_by_business_precompute" not in text
    assert "precompute_pnl_by_business_payloads" not in text
    assert "backend.app.services.pnl_service" not in task_text


def test_api_and_service_layers_do_not_open_writable_duckdb_connections():
    violations: list[str] = []
    for path in _python_sources_under(API_DIR, SERVICES_DIR):
        text = _read_source(path)
        if re.search(r"read_only\s*=\s*False", text) or re.search(r"duckdb\.connect\([^\n]*False", text):
            violations.append(str(path.relative_to(ROOT)))
    assert not violations, "Writable DuckDB connections must live under backend/app/tasks:\n" + "\n".join(violations)


def test_api_and_service_layers_do_not_call_repository_replace_writers():
    violations: list[str] = []
    for path in _python_sources_under(API_DIR, SERVICES_DIR):
        text = _read_source(path)
        calls = _repository_replace_writer_calls(text)
        if calls:
            violations.append(f"{path.relative_to(ROOT)}: {', '.join(calls)}")
    assert not violations, "Repository replace_* writers must be called from backend/app/tasks:\n" + "\n".join(violations)


def test_api_and_service_layers_do_not_open_repository_task_write_scope():
    violations: list[str] = []
    for path in _python_sources_under(API_DIR, SERVICES_DIR):
        text = _read_source(path)
        if "repository_task_write_scope" in text or "require_repository_task_write_scope" in text:
            violations.append(str(path.relative_to(ROOT)))
    assert not violations, "Repository task write scope must only be opened by backend/app/tasks:\n" + "\n".join(violations)


def test_replace_writer_guard_detects_bare_imported_writer_calls():
    calls = _repository_replace_writer_calls(
        """
from backend.app.repositories.cffex_member_rank_repo import replace_member_rank_rows

def service_path(conn, rows):
    return replace_member_rank_rows(conn, rows)
"""
    )
    assert calls == ["replace_member_rank_rows"]


def test_route_duckdb_guard_detects_import_connect_and_exception_handler():
    references = _route_duckdb_references(
        """
import duckdb

def handler(path):
    try:
        return duckdb.connect(path, read_only=True)
    except duckdb.Error:
        return None
"""
    )
    assert references == ["duckdb.connect", "duckdb.exception", "duckdb.import"]


def test_api_routes_do_not_reference_duckdb_directly():
    violations: list[str] = []
    for path in _python_sources_under(API_DIR):
        text = _read_source(path)
        references = _route_duckdb_references(text)
        if references:
            violations.append(f"{path.relative_to(ROOT)}: {', '.join(references)}")
    assert not violations, "DuckDB route reads/errors must be delegated to services:\n" + "\n".join(violations)


def test_health_ready_route_delegates_repository_checks_to_service():
    text = _read_source(HEALTH_ROUTE)
    tree = ast.parse(text)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    call_names = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert not any(module.startswith("backend.app.repositories.") for module in imported_modules)
    assert "healthcheck" not in call_names
    assert "ready_health_payload" in text


def test_macro_vendor_route_delegates_governance_reads_to_service():
    text = _read_source(MACRO_VENDOR_ROUTE)
    tree = ast.parse(text)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not any(module.startswith("backend.app.repositories.") for module in imported_modules)
    assert "GovernanceRepository" not in text
    assert "CACHE_BUILD_RUN_STREAM" not in text
    assert "choice_macro_refresh_status" in text


def test_market_data_livermore_route_delegates_choice_stock_readiness_to_service():
    text = _read_source(MARKET_DATA_LIVERMORE_ROUTE)
    tree = ast.parse(text)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not any(module.startswith("backend.app.repositories.") for module in imported_modules)
    assert "load_choice_stock_readiness" not in text


def test_choice_news_reserved_ingest_route_has_no_service_ingest_path():
    text = _read_source(CHOICE_NEWS_ROUTE)
    tree = ast.parse(text)
    import_scopes: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        if func_name != "ensure_user_allowed":
            continue
        literals = {
            keyword.arg: keyword.value.value
            for keyword in node.keywords
            if keyword.arg in {"resource", "action"}
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        }
        if "resource" in literals and "action" in literals:
            import_scopes.add((literals["resource"], literals["action"]))

    assert "ingest_tushare_npr_to_choice_news" not in text
    assert "_tushare_npr_ingest_handler" not in text
    assert ("choice_news.data", "import") not in import_scopes


def test_adb_analysis_route_keeps_duckdb_reads_in_service_layer():
    text = _read_source(ADB_ANALYSIS_ROUTE)
    assert "import duckdb" not in text
    assert "duckdb.connect" not in text


def test_external_data_route_keeps_duckdb_reads_in_service_layer():
    text = _read_source(EXTERNAL_DATA_ROUTE)
    assert "import duckdb" not in text
    assert "duckdb.connect" not in text


def test_market_data_livermore_route_keeps_duckdb_errors_in_service_layer():
    text = _read_source(MARKET_DATA_LIVERMORE_ROUTE)
    assert "import duckdb" not in text
    assert "except duckdb" not in text
    assert "duckdb.connect" not in text


def test_macro_toolkit_commodity_status_keeps_duckdb_reads_in_service_layer():
    body = _function_source(MACRO_TOOLKIT_ROUTE, "_commodity_futures_status")
    assert "macro_toolkit_service.commodity_futures_status(duckdb_path)" in body
    assert "duckdb.connect" not in body


def test_macro_toolkit_equity_strategy_context_keeps_duckdb_reads_in_service_layer():
    expectations = {
        "_load_equity_strategy_price_context": "macro_toolkit_service.load_equity_strategy_price_context(duckdb_path)",
        "_load_equity_strategy_factor_snapshot": "macro_toolkit_service.load_equity_strategy_factor_snapshot(",
    }
    for function_name, delegated_call in expectations.items():
        body = _function_source(MACRO_TOOLKIT_ROUTE, function_name)
        assert delegated_call in body
        assert "duckdb.connect" not in body


def test_macro_toolkit_a_share_risk_context_keeps_duckdb_reads_in_service_layer():
    body = _function_source(MACRO_TOOLKIT_ROUTE, "_load_a_share_stampede_risk_context")
    assert "macro_toolkit_service.load_a_share_stampede_risk_context(duckdb_path)" in body
    assert "duckdb.connect" not in body


def test_macro_toolkit_curve_rows_keep_duckdb_reads_in_service_layer():
    body = _function_source(MACRO_TOOLKIT_ROUTE, "_load_macro_curve_rows")
    assert "macro_toolkit_service.load_macro_curve_rows(duckdb_path, report_date)" in body
    assert "duckdb.connect" not in body


def test_macro_toolkit_formal_context_readers_keep_duckdb_reads_in_service_layer():
    expectations = {
        "_load_latest_risk_tensor_row": "macro_toolkit_service.load_latest_risk_tensor_row(duckdb_path, report_date)",
        "_load_latest_bond_positions": "macro_toolkit_service.load_latest_bond_positions(duckdb_path, report_date)",
    }
    for function_name, delegated_call in expectations.items():
        body = _function_source(MACRO_TOOLKIT_ROUTE, function_name)
        assert delegated_call in body
        assert "duckdb.connect" not in body
