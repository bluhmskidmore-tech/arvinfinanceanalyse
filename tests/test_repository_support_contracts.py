from __future__ import annotations

from unittest.mock import patch

from tests.helpers import load_module


def test_postgres_mask_dsn_username_password():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract",
        "backend/app/repositories/postgres_repo.py",
    )
    dsn = "postgresql://alice:secret@db.example.com:5432/moss"
    masked = postgres_module._mask_dsn(dsn)
    assert masked == "postgresql://alice:***@db.example.com:5432/moss"
    assert "secret" not in masked
    assert "db.example.com:5432" in masked
    assert masked.endswith("/moss")


def test_postgres_mask_dsn_password_only():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_b",
        "backend/app/repositories/postgres_repo.py",
    )
    dsn = "postgresql://:onlypass@10.0.0.5:5432/appdb"
    masked = postgres_module._mask_dsn(dsn)
    assert masked == "postgresql://***@10.0.0.5:5432/appdb"
    assert "onlypass" not in masked


def test_postgres_mask_dsn_unchanged_without_hostname():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_c",
        "backend/app/repositories/postgres_repo.py",
    )
    bare = "postgresql:///moss"
    assert postgres_module._mask_dsn(bare) == bare
    no_scheme = "not-a-url-at-all"
    assert postgres_module._mask_dsn(no_scheme) == no_scheme


def test_missing_bootstrap_tables_order_and_contents():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_d",
        "backend/app/repositories/postgres_repo.py",
    )
    present = {"public.source_version_registry", "public.cache_manifest"}

    class FakeCursor:
        def execute(self, query: str, params=None) -> None:
            self._params = tuple(params or ())

        def fetchone(self):
            key = self._params[0]
            if key in present:
                return (key,)
            return (None,)

    cursor = FakeCursor()
    missing = postgres_module._missing_bootstrap_tables(cursor)
    assert missing == ["rule_version_registry", "cache_build_run"]


def test_postgres_healthcheck_psycopg_unavailable():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_e",
        "backend/app/repositories/postgres_repo.py",
    )
    with patch.object(postgres_module, "psycopg", None):
        repo = postgres_module.PostgresRepository("postgresql://u:p@127.0.0.1/db")
        result = repo.healthcheck()
    assert result["ok"] is False
    assert result["driver"] == "unavailable"
    assert result["error"] == "psycopg unavailable"


def test_postgres_healthcheck_success_all_bootstrap_visible():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_f",
        "backend/app/repositories/postgres_repo.py",
    )

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query: str, params=None) -> None:
            self._params = tuple(params or ())

        def fetchone(self):
            if self._params == ():
                return (1,)
            return ("public.some_table",)

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    class FakePsycopg:
        @staticmethod
        def connect(dsn: str, *, connect_timeout: float):
            assert connect_timeout == 1.0
            assert "secret" in dsn
            return FakeConnection()

    with patch.object(postgres_module, "psycopg", FakePsycopg):
        repo = postgres_module.PostgresRepository("postgresql://u:secret@127.0.0.1:5432/db")
        result = repo.healthcheck()

    assert result["ok"] is True
    assert result["can_connect"] is True
    assert result["sql_roundtrip"] is True
    assert result["bootstrap_visible"] is True
    assert result["missing_tables"] == []
    assert "secret" not in str(result["dsn"])


def test_postgres_healthcheck_partial_bootstrap():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_g",
        "backend/app/repositories/postgres_repo.py",
    )

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query: str, params=None) -> None:
            self._params = tuple(params or ())

        def fetchone(self):
            if self._params == ():
                return (1,)
            if self._params[0] == "public.source_version_registry":
                return ("public.source_version_registry",)
            return (None,)

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    class FakePsycopg:
        @staticmethod
        def connect(dsn: str, *, connect_timeout: float):
            return FakeConnection()

    with patch.object(postgres_module, "psycopg", FakePsycopg):
        repo = postgres_module.PostgresRepository("postgresql://u:p@h/db")
        result = repo.healthcheck()

    assert result["ok"] is False
    assert result["bootstrap_visible"] is False
    assert result["missing_tables"] == [
        "rule_version_registry",
        "cache_manifest",
        "cache_build_run",
    ]


def test_postgres_healthcheck_connect_exception_message():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_h",
        "backend/app/repositories/postgres_repo.py",
    )

    class Boom(Exception):
        pass

    class FakePsycopg:
        @staticmethod
        def connect(*args, **kwargs):
            raise Boom("nope")

    with patch.object(postgres_module, "psycopg", FakePsycopg):
        repo = postgres_module.PostgresRepository("postgresql://u:p@127.0.0.1/db")
        result = repo.healthcheck()

    assert result["ok"] is False
    assert "Boom" in str(result["error"])
    assert "nope" in str(result["error"])


def test_redis_healthcheck_parses_host_port_and_success(monkeypatch):
    redis_module = load_module(
        "backend.app.repositories.redis_support_contract",
        "backend/app/repositories/redis_repo.py",
    )
    created: list[tuple] = []

    class _Cm:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_create_connection(address, timeout=0.2):
        created.append((address, timeout))
        return _Cm()

    monkeypatch.setattr(redis_module.socket, "create_connection", fake_create_connection)

    dsn = "redis://cache.internal:6380/0"
    repo = redis_module.RedisRepository(dsn)
    result = repo.healthcheck()

    assert result["ok"] is True
    assert result["dsn"] == dsn
    assert created == [(("cache.internal", 6380), 0.2)]


def test_redis_healthcheck_default_port_6379(monkeypatch):
    redis_module = load_module(
        "backend.app.repositories.redis_support_contract_b",
        "backend/app/repositories/redis_repo.py",
    )
    created: list[tuple] = []

    class _Cm:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_create_connection(address, timeout=0.2):
        created.append((address, timeout))
        return _Cm()

    monkeypatch.setattr(redis_module.socket, "create_connection", fake_create_connection)

    repo = redis_module.RedisRepository("redis://localhost/0")
    assert repo.healthcheck()["ok"] is True
    assert created[0][0] == ("localhost", 6379)


def test_redis_healthcheck_oserror_failure(monkeypatch):
    redis_module = load_module(
        "backend.app.repositories.redis_support_contract_c",
        "backend/app/repositories/redis_repo.py",
    )

    def boom(addr, timeout):
        raise OSError("refused")

    monkeypatch.setattr(redis_module.socket, "create_connection", boom)

    dsn = "redis://127.0.0.1:9/0"
    result = redis_module.RedisRepository(dsn).healthcheck()
    assert result["ok"] is False
    assert result["dsn"] == dsn


def test_duckdb_repository_defaults_and_healthcheck_shape():
    duck_module = load_module(
        "backend.app.repositories.duck_support_contract",
        "backend/app/repositories/duckdb_repo.py",
    )
    repo = duck_module.DuckDBRepository("/data/analytics.duckdb")
    assert repo.read_only is True
    h = repo.healthcheck()
    assert h == {"ok": True, "mode": "read_only", "path": "/data/analytics.duckdb"}


def test_duckdb_healthcheck_ignores_read_only_false_field():
    duck_module = load_module(
        "backend.app.repositories.duck_support_contract_b",
        "backend/app/repositories/duckdb_repo.py",
    )
    repo = duck_module.DuckDBRepository("/tmp/x.duckdb", read_only=False)
    assert repo.read_only is False
    assert repo.healthcheck() == {"ok": True, "mode": "read_only", "path": "/tmp/x.duckdb"}
