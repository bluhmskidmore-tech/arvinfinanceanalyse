from dataclasses import dataclass
from urllib.parse import urlparse

try:
    import psycopg
except Exception:  # pragma: no cover - exercised via monkeypatch
    psycopg = None


_BOOTSTRAP_SCHEMA = "public"
_BOOTSTRAP_TABLES = (
    "source_version_registry",
    "rule_version_registry",
    "cache_manifest",
    "cache_build_run",
    "job_run_state",
)


@dataclass
class PostgresRepository:
    dsn: str
    connect_timeout: float = 1.0

    def healthcheck(self) -> dict[str, object]:
        result: dict[str, object] = {
            "ok": False,
            "dsn": _mask_dsn(self.dsn),
            "driver": "psycopg" if psycopg is not None else "unavailable",
            "can_connect": False,
            "sql_roundtrip": False,
            "bootstrap_visible": None,
            "missing_tables": None,
            "error": None,
        }
        if psycopg is None:
            result["error"] = "psycopg unavailable"
            return result

        try:
            with psycopg.connect(self.dsn, connect_timeout=self.connect_timeout) as connection:
                result["can_connect"] = True
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    row = cursor.fetchone()
                    result["sql_roundtrip"] = row == (1,)
                    missing_tables = _missing_bootstrap_tables(cursor)
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
            return result

        result["missing_tables"] = missing_tables
        result["bootstrap_visible"] = not missing_tables
        result["ok"] = bool(result["sql_roundtrip"]) and bool(result["bootstrap_visible"])
        return result


def _mask_dsn(dsn: str) -> str:
    parsed = urlparse(dsn)
    if not parsed.scheme or not parsed.hostname:
        return dsn

    username = parsed.username or ""
    password = parsed.password
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    credentials = username
    if password is not None:
        credentials = f"{credentials}:***" if credentials else "***"
    if credentials:
        netloc = f"{credentials}@{hostname}{port}"
    else:
        netloc = f"{hostname}{port}"
    return parsed._replace(netloc=netloc).geturl()


def _missing_bootstrap_tables(cursor) -> list[str]:
    missing_tables: list[str] = []
    for table_name in _BOOTSTRAP_TABLES:
        cursor.execute("SELECT to_regclass(%s)", (f"{_BOOTSTRAP_SCHEMA}.{table_name}",))
        row = cursor.fetchone()
        if row is None or row[0] is None:
            missing_tables.append(table_name)
    return missing_tables
