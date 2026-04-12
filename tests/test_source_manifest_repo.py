"""Contract tests for backend.app.repositories.source_manifest_repo."""

from __future__ import annotations

from backend.app.repositories.governance_repo import SOURCE_MANIFEST_STREAM
from backend.app.repositories.source_manifest_repo import (
    MANIFEST_ELIGIBLE_STATUSES,
    SOURCE_MANIFEST_SCHEMA_VERSION,
    SourceManifestRepository,
)


class _FakeGovernanceRepo:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []
        self.append_calls: list[tuple[str, dict[str, object]]] = []

    def read_all(self, stream_name: str) -> list[dict[str, object]]:
        assert stream_name == SOURCE_MANIFEST_STREAM
        return list(self.rows)

    def append_many_atomic(self, items: list[tuple[str, dict[str, object]]]) -> None:
        for stream_name, record in items:
            assert stream_name == SOURCE_MANIFEST_STREAM
            self.append_calls.append((stream_name, record))
            self.rows.append(record)


def _base_row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "source_family": "zqtz",
        "report_date": "2025-12-31",
        "source_file": "ZQTZSHOW-20251231.xls",
        "source_version": "v1",
        "ingest_batch_id": "ib-1",
        "archived_path": "/tmp/a.xls",
    }
    base.update(overrides)
    return base


def test_add_many_empty_repo_sets_schema_status_completed_and_created_at():
    repo = SourceManifestRepository()
    out = repo.add_many(
        [
            {
                "source_family": "zqtz",
                "report_date": "2025-12-31",
                "source_file": "f.xls",
                "source_version": "sv",
                "ingest_batch_id": "ib-a",
            }
        ]
    )
    assert len(out) == 1
    row = out[0]
    assert row["schema_version"] == SOURCE_MANIFEST_SCHEMA_VERSION
    assert row["status"] == "completed"
    assert isinstance(row["created_at"], str) and row["created_at"]
    assert repo.load_all() == out


def test_add_many_second_same_identity_is_rerun_with_rerun_of_batch_id():
    repo = SourceManifestRepository()
    first = repo.add_many(
        [
            {
                "source_family": "zqtz",
                "report_date": "2025-12-31",
                "source_file": "same.xls",
                "source_version": "sv",
                "ingest_batch_id": "ib-first",
            }
        ]
    )
    second = repo.add_many(
        [
            {
                "source_family": "zqtz",
                "report_date": "2025-12-31",
                "source_file": "same.xls",
                "source_version": "sv",
                "ingest_batch_id": "ib-second",
            }
        ]
    )
    assert first[0]["ingest_batch_id"] == "ib-first"
    assert second[0]["status"] == "rerun"
    assert second[0]["rerun_of_batch_id"] == "ib-first"


def test_load_all_uses_governance_repo_when_set():
    inner = _FakeGovernanceRepo()
    inner.rows = [{"ingest_batch_id": "x", "from": "gov"}]
    repo = SourceManifestRepository(rows=[{"ingest_batch_id": "y", "from": "memory"}], governance_repo=inner)
    assert repo.load_all() == inner.rows


def test_load_by_batch_filters_by_ingest_batch_id():
    repo = SourceManifestRepository()
    repo.add_many([_base_row(ingest_batch_id="b1"), _base_row(ingest_batch_id="b2", source_file="other.xls")])
    rows = repo.load_by_batch("b2")
    assert len(rows) == 1
    assert rows[0]["ingest_batch_id"] == "b2"


def test_add_many_persists_via_governance_repo_when_configured():
    gov = _FakeGovernanceRepo()
    repo = SourceManifestRepository(governance_repo=gov)
    persisted = repo.add_many(
        [
            {
                "source_family": "zqtz",
                "report_date": "2025-12-31",
                "source_file": "g.xls",
                "source_version": "sv",
                "ingest_batch_id": "ib-g",
            }
        ]
    )
    assert gov.rows == persisted
    assert len(gov.append_calls) == 1
    assert gov.append_calls[0][1]["ingest_batch_id"] == "ib-g"


def test_select_by_ingest_batch_id_matches_select_for_snapshot_materialization():
    repo = SourceManifestRepository()
    repo.add_many(
        [
            _base_row(ingest_batch_id="target", archived_path="/z/a"),
            _base_row(ingest_batch_id="other", archived_path="/z/b", source_file="b.xls"),
        ]
    )
    a = repo.select_by_ingest_batch_id("target")
    b = repo.select_for_snapshot_materialization(ingest_batch_id="target")
    assert a == b


def test_select_for_snapshot_materialization_requires_eligible_status_and_archived_path():
    repo = SourceManifestRepository()
    repo.rows = [
        {
            "source_family": "zqtz",
            "report_date": "2025-12-31",
            "status": "failed",
            "archived_path": "/a",
            "ingest_batch_id": "1",
            "created_at": "t1",
        },
        {
            "source_family": "zqtz",
            "report_date": "2025-12-31",
            "status": "completed",
            "ingest_batch_id": "2",
            "created_at": "t2",
        },
    ]
    assert repo.select_for_snapshot_materialization() == []


def test_select_filters_source_families_and_report_date():
    repo = SourceManifestRepository()
    repo.rows = [
        _base_row(
            source_family="zqtz",
            report_date="2025-12-31",
            archived_path="/1",
            ingest_batch_id="a",
            status="completed",
        ),
        _base_row(
            source_family="tyw",
            report_date="2025-12-31",
            archived_path="/2",
            ingest_batch_id="b",
            source_file="t.xls",
            status="completed",
        ),
        _base_row(
            source_family="zqtz",
            report_date="2025-11-30",
            archived_path="/3",
            ingest_batch_id="c",
            source_file="older.xls",
            status="completed",
        ),
    ]
    z = repo.select_for_snapshot_materialization(source_families=["zqtz"], report_date="2025-12-31")
    assert {r["ingest_batch_id"] for r in z} == {"a"}


def test_select_latest_per_family_uses_max_created_at_and_ingest_batch_id():
    repo = SourceManifestRepository()
    repo.rows = [
        _base_row(
            ingest_batch_id="old",
            archived_path="/x/old",
            created_at="2025-01-01T00:00:00+00:00",
            status="completed",
        ),
        _base_row(
            ingest_batch_id="new",
            archived_path="/x/new",
            created_at="2025-02-01T00:00:00+00:00",
            status="completed",
        ),
    ]
    out = repo.select_for_snapshot_materialization(source_families=["zqtz"], report_date="2025-12-31")
    ids = {r["ingest_batch_id"] for r in out}
    assert ids == {"new"}


def test_select_by_source_family_and_report_date_delegate_to_select_for_snapshot_materialization():
    repo = SourceManifestRepository()
    repo.rows = [
        _base_row(source_family="tyw", archived_path="/p/1", ingest_batch_id="i1", source_file="tyw.xls"),
    ]
    a = repo.select_by_source_family("tyw", report_date="2025-12-31")
    b = repo.select_for_snapshot_materialization(source_families=["tyw"], report_date="2025-12-31")
    assert a == b


def test_manifest_eligible_statuses_frozen():
    assert MANIFEST_ELIGIBLE_STATUSES == frozenset({"completed", "rerun"})


def test_latest_summary():
    repo = SourceManifestRepository()
    assert repo.latest_summary() == {"row_count": 0, "last_row": None}
    repo.add_many([_base_row(ingest_batch_id="z")])
    summary = repo.latest_summary()
    assert summary["row_count"] == 1
    assert summary["last_row"]["ingest_batch_id"] == "z"
