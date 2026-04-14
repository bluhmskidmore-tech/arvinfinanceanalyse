from pathlib import Path

from tests.helpers import load_module


def test_network_backed_repositories_report_unreachable_endpoints_as_not_ok():
    postgres_module = load_module("backend.app.repositories.postgres_repo", "backend/app/repositories/postgres_repo.py")
    redis_module = load_module("backend.app.repositories.redis_repo", "backend/app/repositories/redis_repo.py")
    object_store_module = load_module("backend.app.repositories.object_store_repo", "backend/app/repositories/object_store_repo.py")

    postgres_repo = postgres_module.PostgresRepository("postgresql://u:p@127.0.0.1:1/db")
    redis_repo = redis_module.RedisRepository("redis://127.0.0.1:1/0")
    object_store_repo = object_store_module.ObjectStoreRepository(
        endpoint="127.0.0.1:1",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="moss-artifacts",
    )

    assert postgres_repo.healthcheck()["ok"] is False
    assert redis_repo.healthcheck()["ok"] is False
    assert object_store_repo.healthcheck()["ok"] is False


def test_local_archive_object_store_mode_is_healthy_without_minio(tmp_path):
    object_store_module = load_module("backend.app.repositories.object_store_repo", "backend/app/repositories/object_store_repo.py")

    object_store_repo = object_store_module.ObjectStoreRepository(
        endpoint="127.0.0.1:1",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="moss-artifacts",
        mode="local",
        local_archive_path=str(tmp_path / "archive"),
    )

    result = object_store_repo.healthcheck()
    assert result["ok"] is True
    assert result["mode"] == "local"


def test_local_archive_mode_copies_file_into_archive_directory(tmp_path):
    object_store_module = load_module("backend.app.repositories.object_store_repo", "backend/app/repositories/object_store_repo.py")
    source_file = tmp_path / "source.txt"
    source_file.write_text("demo", encoding="utf-8")

    object_store_repo = object_store_module.ObjectStoreRepository(
        endpoint="127.0.0.1:1",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="moss-artifacts",
        mode="local",
        local_archive_path=str(tmp_path / "archive"),
    )

    archived = object_store_repo.archive_file(source_file, source_name="demo-source")
    archived_path = Path(archived["archived_path"])
    assert archived["mode"] == "local"
    assert archived_path.exists()
    assert archived_path.read_text(encoding="utf-8") == "demo"


def test_local_archive_mode_uses_distinct_paths_for_sanitized_name_collisions(tmp_path):
    object_store_module = load_module("backend.app.repositories.object_store_repo", "backend/app/repositories/object_store_repo.py")
    first_source = tmp_path / "north" / "quarterly report.csv"
    second_source = tmp_path / "south" / "quarterly@report.csv"
    first_source.parent.mkdir(parents=True, exist_ok=True)
    second_source.parent.mkdir(parents=True, exist_ok=True)
    first_source.write_text("north", encoding="utf-8")
    second_source.write_text("south", encoding="utf-8")

    object_store_repo = object_store_module.ObjectStoreRepository(
        endpoint="127.0.0.1:1",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="moss-artifacts",
        mode="local",
        local_archive_path=str(tmp_path / "archive"),
    )

    first_archived = object_store_repo.archive_file(first_source, source_name="demo-source")
    second_archived = object_store_repo.archive_file(second_source, source_name="demo-source")

    first_archived_path = Path(first_archived["archived_path"])
    second_archived_path = Path(second_archived["archived_path"])

    assert first_archived_path != second_archived_path
    assert first_archived_path.read_text(encoding="utf-8") == "north"
    assert second_archived_path.read_text(encoding="utf-8") == "south"


def test_local_archive_mode_keeps_repeat_archives_immutable_across_ingest_batches(tmp_path):
    object_store_module = load_module("backend.app.repositories.object_store_repo", "backend/app/repositories/object_store_repo.py")
    source_file = tmp_path / "desk-a" / "positions.csv"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("first-run", encoding="utf-8")

    object_store_repo = object_store_module.ObjectStoreRepository(
        endpoint="127.0.0.1:1",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="moss-artifacts",
        mode="local",
        local_archive_path=str(tmp_path / "archive"),
    )

    first_archived = object_store_repo.archive_file(
        source_file,
        source_name="demo-source",
        source_key="desk-a/positions.csv",
        ingest_batch_id="batch-001",
    )

    source_file.write_text("second-run", encoding="utf-8")

    second_archived = object_store_repo.archive_file(
        source_file,
        source_name="demo-source",
        source_key="desk-a/positions.csv",
        ingest_batch_id="batch-002",
    )

    first_archived_path = Path(first_archived["archived_path"])
    second_archived_path = Path(second_archived["archived_path"])

    assert first_archived_path != second_archived_path
    assert first_archived_path.exists()
    assert second_archived_path.exists()
    assert first_archived_path.read_text(encoding="utf-8") == "first-run"
    assert second_archived_path.read_text(encoding="utf-8") == "second-run"


def test_local_archive_mode_keeps_direct_repository_archives_immutable_without_ingest_batch_id(tmp_path):
    object_store_module = load_module("backend.app.repositories.object_store_repo", "backend/app/repositories/object_store_repo.py")
    source_file = tmp_path / "desk-a" / "positions.csv"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("first-run", encoding="utf-8")

    object_store_repo = object_store_module.ObjectStoreRepository(
        endpoint="127.0.0.1:1",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="moss-artifacts",
        mode="local",
        local_archive_path=str(tmp_path / "archive"),
    )

    first_archived = object_store_repo.archive_file(
        source_file,
        source_name="demo-source",
        source_key="desk-a/positions.csv",
    )

    source_file.write_text("second-run", encoding="utf-8")

    second_archived = object_store_repo.archive_file(
        source_file,
        source_name="demo-source",
        source_key="desk-a/positions.csv",
    )

    first_archived_path = Path(first_archived["archived_path"])
    second_archived_path = Path(second_archived["archived_path"])

    assert first_archived_path != second_archived_path
    assert first_archived["ingest_batch_id"]
    assert second_archived["ingest_batch_id"]
    assert first_archived["ingest_batch_id"] != second_archived["ingest_batch_id"]
    assert first_archived_path.exists()
    assert second_archived_path.exists()
    assert first_archived_path.read_text(encoding="utf-8") == "first-run"
    assert second_archived_path.read_text(encoding="utf-8") == "second-run"


def test_local_archive_object_store_healthcheck_reports_not_ok_when_archive_path_is_a_file(tmp_path):
    object_store_module = load_module("backend.app.repositories.object_store_repo", "backend/app/repositories/object_store_repo.py")
    archive_path = tmp_path / "archive"
    archive_path.write_text("not-a-directory", encoding="utf-8")

    object_store_repo = object_store_module.ObjectStoreRepository(
        endpoint="127.0.0.1:1",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="moss-artifacts",
        mode="local",
        local_archive_path=str(archive_path),
    )

    result = object_store_repo.healthcheck()

    assert result["ok"] is False
    assert result["mode"] == "local"
    assert result["path"] == str(archive_path)


def test_postgres_healthcheck_masks_password_and_reports_driver_unavailable(monkeypatch):
    postgres_module = load_module("backend.app.repositories.postgres_repo", "backend/app/repositories/postgres_repo.py")
    monkeypatch.setattr(postgres_module, "psycopg", None)

    postgres_repo = postgres_module.PostgresRepository("postgresql://moss:super-secret@127.0.0.1:5432/moss")

    result = postgres_repo.healthcheck()

    assert result["ok"] is False
    assert result["driver"] == "unavailable"
    assert result["dsn"] == "postgresql://moss:***@127.0.0.1:5432/moss"
    assert "super-secret" not in result["dsn"]
    assert result["can_connect"] is False
    assert result["sql_roundtrip"] is False
    assert result["bootstrap_visible"] is None


def test_postgres_healthcheck_requires_sql_roundtrip_and_reports_missing_bootstrap(monkeypatch):
    postgres_module = load_module("backend.app.repositories.postgres_repo", "backend/app/repositories/postgres_repo.py")
    calls: list[tuple[str, float]] = []

    class FakeCursor:
        def __init__(self) -> None:
            self._last_params: tuple[str, ...] | None = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query: str, params=None) -> None:
            if "SELECT 1" in query:
                self._last_params = None
                return
            self._last_params = tuple(params or ())

        def fetchone(self):
            if self._last_params is None:
                return (1,)
            table = self._last_params[0]
            if table in {"public.source_version_registry", "public.cache_manifest"}:
                return (table,)
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
            calls.append((dsn, connect_timeout))
            return FakeConnection()

    monkeypatch.setattr(postgres_module, "psycopg", FakePsycopg)

    postgres_repo = postgres_module.PostgresRepository("postgresql://moss:moss@127.0.0.1:5432/moss")

    result = postgres_repo.healthcheck()

    assert calls == [("postgresql://moss:moss@127.0.0.1:5432/moss", 1.0)]
    assert result["ok"] is False
    assert result["driver"] == "psycopg"
    assert result["can_connect"] is True
    assert result["sql_roundtrip"] is True
    assert result["bootstrap_visible"] is False
    assert result["missing_tables"] == [
        "rule_version_registry",
        "cache_build_run",
        "job_run_state",
    ]
