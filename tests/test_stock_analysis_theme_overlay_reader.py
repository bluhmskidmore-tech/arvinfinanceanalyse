from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.app.repositories.governance_repo import (
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.stock_analysis_theme_overlay_reader import (
    StockAnalysisThemeOverlayReader,
    THEME_OVERLAY_CACHE_KEY,
    ThemeOverlayManifestAccessor,
)
from backend.app.schemas.materialize import CacheManifestRecord
from backend.app.schemas.stock_analysis_theme_overlay import (
    ThemeOverlayArchiveContent,
    ThemeOverlayArchiveDocument,
    canonical_theme_overlay_document_bytes,
    compute_theme_overlay_content_hash,
    compute_theme_overlay_lineage_hash,
)
from backend.app.tasks.stock_analysis_theme_overlay_archive import (
    CHOICE_STOCK_OBSERVATION_CACHE_KEY,
    archive_tushare_ths_current_overlay,
)


def _archive_fixture(tmp_path: Path) -> tuple[StockAnalysisThemeOverlayReader, Path]:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    repo = GovernanceRepository(base_dir=governance_dir)
    repo.append(
        CACHE_MANIFEST_STREAM,
        CacheManifestRecord(
            cache_key=CHOICE_STOCK_OBSERVATION_CACHE_KEY,
            cache_version="choice_stock_refresh_v1",
            source_version="sv_choice_stock_current",
            vendor_version="vv_choice_stock_current",
            rule_version="rv_choice_stock_materialization_front_layer_v1",
            basis="observational",
            module_name="choice_stock",
            result_kind_family="choice-stock-observation",
            run_id="choice_stock_refresh:2026-07-08:fixture",
            report_date="2026-07-08",
            input_sources=["choice_stock_materialization"],
            fact_tables=["choice_stock_daily_observation"],
            lineage={
                "materialization_run_id": "choice_stock_materialize:2026-07-08:fixture",
                "refresh_run_id": "choice_stock_refresh:2026-07-08:fixture",
                "materialization_status": "completed",
                "daily_observation_report_date": "2026-07-08",
                "daily_observation_row_count": 2,
                "materialized_row_count": 2,
                "stock_code_count": 2,
            },
            created_at="2026-07-08T23:00:00Z",
        ).model_dump(),
    )
    archived = archive_tushare_ths_current_overlay(
        governance_dir=governance_dir,
        governance_repo=repo,
        archive_root=archive_root,
        load_members=lambda: [
            {
                "stock_code": "000001.SZ",
                "stock_name": "Ping An Bank",
                "theme_key": "885002.TI",
                "theme_name": "Financial technology",
            },
            {
                "stock_code": "000002.SZ",
                "stock_name": "Vanke A",
                "theme_key": "885001.TI",
                "theme_name": "Low-altitude economy",
            },
        ],
        run_id="theme-overlay:2026-07-08:fixture",
        source_version="sv_tushare_ths_fixture",
        vendor_version="vv_tushare_ths_fixture",
        membership_observed_at=datetime(2026, 7, 9, 1, tzinfo=UTC),
    )
    assert archived.status == "completed"
    return (
        StockAnalysisThemeOverlayReader(
            archive_root=archive_root,
            governance_repo=repo,
        ),
        Path(archived.archived_path or ""),
    )


def test_current_overlay_is_available_only_for_the_matching_observation_date(
    tmp_path: Path,
) -> None:
    reader, _ = _archive_fixture(tmp_path)

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert result.status == "available"
    assert result.reason == "current_overlay_available"
    assert result.report_date == "2026-07-08"
    assert result.source_kind == "tushare_ths_current_overlay"
    assert result.concept_source_kind == "tushare_current_overlay"
    assert result.source_version == "sv_tushare_ths_fixture"
    assert result.vendor_version == "vv_tushare_ths_fixture"
    assert result.point_in_time is False
    assert result.historical_use_allowed is False
    assert [member.stock_code for member in result.members] == [
        "000001.SZ",
        "000002.SZ",
    ]
    assert len(result.fingerprint) == 64
    assert reader.fingerprint() == reader.fingerprint()


def test_read_uses_one_date_anchored_manifest_snapshot(tmp_path: Path) -> None:
    reader, _ = _archive_fixture(tmp_path)
    delegate = reader.governance_repo
    calls: list[tuple[str, str | None]] = []

    class CountingManifestAccessor:
        def read_latest_manifest(
            self,
            cache_key: str,
            *,
            report_date: str | None = None,
        ) -> dict[str, object] | None:
            calls.append((cache_key, report_date))
            return delegate.read_latest_manifest(
                cache_key,
                report_date=report_date,
            )

    counted_reader = StockAnalysisThemeOverlayReader(
        archive_root=reader.archive_root,
        governance_repo=CountingManifestAccessor(),  # type: ignore[arg-type]
    )

    result = counted_reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert result.status == "available"
    assert result.fingerprint == counted_reader.fingerprint()
    assert calls[:2] == [
        (CHOICE_STOCK_OBSERVATION_CACHE_KEY, None),
        (THEME_OVERLAY_CACHE_KEY, "2026-07-08"),
    ]
    # The explicit fingerprint check above is a separate call; read itself used two reads.
    assert len(calls) == 4


def test_pure_read_accessor_reads_existing_jsonl_and_sql_authority(
    tmp_path: Path,
) -> None:
    writer_reader, _ = _archive_fixture(tmp_path)
    manifest_path = tmp_path / "governance" / "cache_manifest.jsonl"
    manifest_bytes = manifest_path.read_bytes()
    jsonl_reader = StockAnalysisThemeOverlayReader(
        archive_root=tmp_path / "archive",
        governance_repo=ThemeOverlayManifestAccessor(
            base_dir=tmp_path / "governance",
            backend_mode="jsonl",
        ),
    )

    jsonl_result = jsonl_reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert jsonl_result.status == "available"
    assert manifest_path.read_bytes() == manifest_bytes

    sqlite_path = tmp_path / "governance-authority.db"
    sql_repo = GovernanceRepository(
        base_dir=tmp_path / "sql-shadow",
        sql_dsn=f"sqlite:///{sqlite_path.as_posix()}",
        backend_mode="sql-authority",
    )
    for manifest in writer_reader.governance_repo.read_all(CACHE_MANIFEST_STREAM):
        sql_repo.append(CACHE_MANIFEST_STREAM, manifest)
    sql_reader = StockAnalysisThemeOverlayReader(
        archive_root=tmp_path / "archive",
        governance_repo=ThemeOverlayManifestAccessor(
            base_dir=tmp_path / "unused-jsonl",
            sql_dsn=f"sqlite:///{sqlite_path.as_posix()}",
            backend_mode="sql-authority",
        ),
    )

    sql_result = sql_reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert sql_result.status == "available"


def test_jsonl_accessor_reuses_unchanged_index_and_invalidates_after_append(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, _ = _archive_fixture(tmp_path)
    governance_dir = tmp_path / "governance"
    manifest_path = governance_dir / "cache_manifest.jsonl"
    accessor = ThemeOverlayManifestAccessor(base_dir=governance_dir)
    original_read_text = Path.read_text
    manifest_read_count = 0

    def counted_read_text(path: Path, *args, **kwargs) -> str:
        nonlocal manifest_read_count
        if path.resolve() == manifest_path.resolve():
            manifest_read_count += 1
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted_read_text)

    first = accessor.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY)
    second = accessor.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY)
    overlay = accessor.read_latest_manifest(
        THEME_OVERLAY_CACHE_KEY,
        report_date="2026-07-08",
    )

    assert first == second
    assert overlay is not None
    assert manifest_read_count == 1

    assert first is not None
    revised = dict(first)
    revised["source_version"] = "sv_choice_stock_cache_invalidation"
    revised["run_id"] = "choice_stock_refresh:2026-07-08:cache-invalidation"
    revised_lineage = dict(revised["lineage"])
    revised_lineage["refresh_run_id"] = revised["run_id"]
    revised["lineage"] = revised_lineage
    reader.governance_repo.append(CACHE_MANIFEST_STREAM, revised)

    refreshed = accessor.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY)

    assert refreshed is not None
    assert refreshed["source_version"] == "sv_choice_stock_cache_invalidation"
    assert manifest_read_count == 2


def test_sqlite_authority_read_creates_no_sidecars_while_connection_is_live(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import event

    from backend.app.repositories import (
        stock_analysis_theme_overlay_reader as reader_module,
    )

    sqlite_path = tmp_path / "wal-authority.db"
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute("pragma journal_mode=wal")
        conn.execute(
            "create table cache_manifest "
            "(row_id integer primary key autoincrement, cache_key text, payload_json text)"
        )
        conn.execute(
            "insert into cache_manifest (cache_key, payload_json) values (?, ?)",
            ["fixture.key", json.dumps({"cache_key": "fixture.key", "value": "ready"})],
        )
        conn.commit()
        conn.execute("pragma wal_checkpoint(truncate)")
    sidecar_paths = [
        Path(f"{sqlite_path}-wal"),
        Path(f"{sqlite_path}-shm"),
    ]
    before = {
        path: path.read_bytes() if path.exists() else None for path in sidecar_paths
    }
    observed_while_connected: list[dict[Path, bytes | None]] = []
    real_create_engine = reader_module.create_engine

    def observing_create_engine(*args: object, **kwargs: object):
        engine = real_create_engine(*args, **kwargs)
        event.listen(
            engine,
            "after_cursor_execute",
            lambda *_args: observed_while_connected.append(
                {
                    path: path.read_bytes() if path.exists() else None
                    for path in sidecar_paths
                }
            ),
        )
        return engine

    monkeypatch.setattr(reader_module, "create_engine", observing_create_engine)
    accessor = ThemeOverlayManifestAccessor(
        base_dir=tmp_path / "unused-jsonl",
        sql_dsn=f"sqlite:///{sqlite_path.as_posix()}",
        backend_mode="sql-authority",
    )

    result = accessor.read_latest_manifest("fixture.key")

    assert result == {"cache_key": "fixture.key", "value": "ready"}
    assert observed_while_connected
    assert all(snapshot == before for snapshot in observed_while_connected)
    assert {
        path: path.read_bytes() if path.exists() else None for path in sidecar_paths
    } == before


def test_sqlite_authority_missing_database_fails_closed_without_creating_files(
    tmp_path: Path,
) -> None:
    sqlite_path = tmp_path / "missing-authority.db"
    accessor = ThemeOverlayManifestAccessor(
        base_dir=tmp_path / "unused-jsonl",
        sql_dsn=f"sqlite:///{sqlite_path.as_posix()}",
        backend_mode="sql-authority",
    )

    result = accessor.read_latest_manifest("fixture.key")

    assert result is None
    assert not sqlite_path.exists()
    assert not Path(f"{sqlite_path}-wal").exists()
    assert not Path(f"{sqlite_path}-shm").exists()


def test_sqlite_authority_uncheckpointed_wal_fails_closed_without_mutation(
    tmp_path: Path,
) -> None:
    sqlite_path = tmp_path / "uncheckpointed-authority.db"
    writer = sqlite3.connect(sqlite_path)
    try:
        writer.execute("pragma journal_mode=wal")
        writer.execute("pragma wal_autocheckpoint=0")
        writer.execute(
            "create table cache_manifest "
            "(row_id integer primary key autoincrement, cache_key text, payload_json text)"
        )
        writer.execute(
            "insert into cache_manifest (cache_key, payload_json) values (?, ?)",
            ["fixture.key", json.dumps({"cache_key": "fixture.key", "value": "old"})],
        )
        writer.commit()
        writer.execute("pragma wal_checkpoint(truncate)")
        writer.execute(
            "insert into cache_manifest (cache_key, payload_json) values (?, ?)",
            [
                "fixture.key",
                json.dumps({"cache_key": "fixture.key", "value": "latest"}),
            ],
        )
        writer.commit()
        sidecar_paths = [
            Path(f"{sqlite_path}-wal"),
            Path(f"{sqlite_path}-shm"),
        ]
        assert sidecar_paths[0].stat().st_size > 0
        before = {path: path.read_bytes() for path in sidecar_paths}
        accessor = ThemeOverlayManifestAccessor(
            base_dir=tmp_path / "unused-jsonl",
            sql_dsn=f"sqlite:///{sqlite_path.as_posix()}",
            backend_mode="sql-authority",
        )

        with pytest.raises(ValueError, match="uncheckpointed SQLite WAL"):
            accessor.read_latest_manifest("fixture.key")

        assert {path: path.read_bytes() for path in sidecar_paths} == before
    finally:
        writer.close()


def test_sql_authority_latest_identity_mismatch_never_falls_back_to_older_row(
    tmp_path: Path,
) -> None:
    sqlite_path = tmp_path / "identity-mismatch-authority.db"
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(
            "create table cache_manifest "
            "(row_id integer primary key autoincrement, cache_key text, payload_json text)"
        )
        conn.executemany(
            "insert into cache_manifest (cache_key, payload_json) values (?, ?)",
            [
                (
                    "fixture.key",
                    json.dumps({"cache_key": "fixture.key", "value": "old-good"}),
                ),
                (
                    "fixture.key",
                    json.dumps({"cache_key": "other.key", "value": "latest-bad"}),
                ),
            ],
        )
    accessor = ThemeOverlayManifestAccessor(
        base_dir=tmp_path / "unused-jsonl",
        sql_dsn=f"sqlite:///{sqlite_path.as_posix()}",
        backend_mode="sql-authority",
    )

    with pytest.raises(ValueError, match="SQL identity mismatch"):
        accessor.read_latest_manifest("fixture.key")


@pytest.mark.parametrize(
    ("requested_as_of_date", "effective_as_of_date"),
    [
        ("2026-07-07", "2026-07-07"),
        ("2026-07-09", "2026-07-08"),
        ("2026-07-08", "2026-07-07"),
    ],
)
def test_historical_or_fallback_request_never_sees_current_overlay(
    tmp_path: Path,
    requested_as_of_date: str,
    effective_as_of_date: str,
) -> None:
    reader, _ = _archive_fixture(tmp_path)

    result = reader.read(
        requested_as_of_date=requested_as_of_date,
        effective_as_of_date=effective_as_of_date,
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_hidden_for_noncurrent_request"
    assert result.members == ()


def test_request_without_resolved_market_date_never_sees_current_overlay(
    tmp_path: Path,
) -> None:
    reader, _ = _archive_fixture(tmp_path)

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date=None,
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_hidden_without_resolved_market_date"
    assert result.members == ()


@pytest.mark.parametrize(
    ("evaluation_time", "expected_reason"),
    [
        (
            datetime(2026, 7, 8, 22, 59, tzinfo=UTC),
            "observation anchor created_at is after evaluation_time",
        ),
        (
            datetime(2026, 7, 9, 0, 59, tzinfo=UTC),
            "membership_observed_at is after evaluation_time",
        ),
    ],
)
def test_future_observation_or_capture_time_is_hidden(
    tmp_path: Path,
    evaluation_time: datetime,
    expected_reason: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    reader, _ = _archive_fixture(tmp_path)

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=evaluation_time,
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_invalid"
    assert expected_reason in caplog.text
    assert result.members == ()


def test_backfill_mode_suppresses_before_governance_or_archive_reads(
    tmp_path: Path,
) -> None:
    class ExplodingGovernanceRepo:
        def read_latest_manifest(self, _cache_key: str):
            raise AssertionError("governance must not be read in backfill mode")

    reader = StockAnalysisThemeOverlayReader(
        archive_root=tmp_path / "missing-archive",
        governance_repo=ExplodingGovernanceRepo(),  # type: ignore[arg-type]
    )

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        backfill_mode=True,
    )

    assert result.status == "suppressed"
    assert result.members == ()
    assert reader.fingerprint(backfill_mode=True) == result.fingerprint


@pytest.mark.parametrize(
    "corruption", ["invalid_json", "noncanonical_json", "stale_hash"]
)
def test_corrupt_noncanonical_or_hash_mismatched_archive_fails_closed(
    tmp_path: Path,
    corruption: str,
) -> None:
    reader, archived_path = _archive_fixture(tmp_path)
    raw = archived_path.read_bytes()
    if corruption == "invalid_json":
        archived_path.write_bytes(b"{")
    elif corruption == "noncanonical_json":
        archived_path.write_bytes(raw + b"\n")
    else:
        payload = json.loads(raw)
        payload["members"][0]["stock_name"] = "Tampered name"
        archived_path.write_text(
            json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
            encoding="utf-8",
        )

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_invalid"
    assert result.members == ()


def test_manifest_document_lineage_mismatch_fails_closed(tmp_path: Path) -> None:
    reader, _ = _archive_fixture(tmp_path)
    latest = reader.governance_repo.read_latest_manifest(
        "stock-analysis.theme-overlay.tushare-ths-current"
    )
    assert latest is not None
    mismatched = dict(latest)
    mismatched["source_version"] = "sv_different_overlay"
    reader.governance_repo.append(CACHE_MANIFEST_STREAM, mismatched)

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_invalid"
    assert result.members == ()


@pytest.mark.parametrize("tampering", ["missing", "mismatch"])
def test_overlay_manifest_observation_anchor_must_match_document_and_observation(
    tmp_path: Path,
    tampering: str,
) -> None:
    reader, _ = _archive_fixture(tmp_path)
    latest = reader.governance_repo.read_latest_manifest(
        "stock-analysis.theme-overlay.tushare-ths-current"
    )
    assert latest is not None
    tampered = json.loads(json.dumps(latest))
    lineage = tampered["lineage"]
    if tampering == "missing":
        lineage.pop("observation_anchor")
    else:
        lineage["observation_anchor"]["source_version"] = "sv_tampered_anchor"
    reader.governance_repo.append(CACHE_MANIFEST_STREAM, tampered)

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_invalid"
    assert result.members == ()


def test_overlay_manifest_created_at_must_equal_membership_observed_at(
    tmp_path: Path,
) -> None:
    reader, _ = _archive_fixture(tmp_path)
    latest = reader.governance_repo.read_latest_manifest(
        "stock-analysis.theme-overlay.tushare-ths-current"
    )
    assert latest is not None
    tampered = json.loads(json.dumps(latest))
    tampered["created_at"] = "2026-07-09T01:01:00Z"
    reader.governance_repo.append(CACHE_MANIFEST_STREAM, tampered)

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_invalid"
    assert result.members == ()


def test_rehashed_archive_market_date_cannot_postdate_membership_capture(
    tmp_path: Path,
) -> None:
    reader, archived_path = _archive_fixture(tmp_path)
    raw_payload = json.loads(archived_path.read_text(encoding="utf-8"))
    raw_payload.pop("content_hash")
    raw_payload.pop("lineage_hash")
    raw_payload["membership_observed_at"] = "2026-07-07T01:00:00Z"
    raw_payload["observation_anchor"]["created_at"] = "2026-07-07T00:00:00Z"
    content = ThemeOverlayArchiveContent.model_validate(raw_payload)
    document = ThemeOverlayArchiveDocument(
        **content.model_dump(),
        content_hash=compute_theme_overlay_content_hash(content),
        lineage_hash=compute_theme_overlay_lineage_hash(content),
    )
    malicious_path = archived_path.with_name(
        f"theme-overlay__{document.content_hash}.json"
    )
    malicious_path.write_bytes(canonical_theme_overlay_document_bytes(document))

    observation = reader.governance_repo.read_latest_manifest(
        CHOICE_STOCK_OBSERVATION_CACHE_KEY
    )
    overlay = reader.governance_repo.read_latest_manifest(
        "stock-analysis.theme-overlay.tushare-ths-current"
    )
    assert observation is not None
    assert overlay is not None
    revised_observation = json.loads(json.dumps(observation))
    revised_observation["created_at"] = "2026-07-07T00:00:00Z"
    revised_overlay = json.loads(json.dumps(overlay))
    revised_overlay["created_at"] = "2026-07-07T01:00:00Z"
    revised_overlay["lineage"].update(
        {
            "archived_path": str(malicious_path),
            "membership_observed_at": document.membership_observed_at.isoformat(),
            "content_hash": document.content_hash,
            "lineage_hash": document.lineage_hash,
            "observation_anchor": document.observation_anchor.model_dump(mode="json"),
        }
    )
    reader.governance_repo.append(CACHE_MANIFEST_STREAM, revised_observation)
    reader.governance_repo.append(CACHE_MANIFEST_STREAM, revised_overlay)

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_invalid"
    assert result.members == ()


def test_rehashed_archive_anchor_cannot_postdate_membership_capture(
    tmp_path: Path,
) -> None:
    reader, archived_path = _archive_fixture(tmp_path)
    raw_payload = json.loads(archived_path.read_text(encoding="utf-8"))
    raw_payload.pop("content_hash")
    raw_payload.pop("lineage_hash")
    raw_payload["observation_anchor"]["created_at"] = "2026-07-09T02:00:00Z"
    content = ThemeOverlayArchiveContent.model_validate(raw_payload)
    document = ThemeOverlayArchiveDocument(
        **content.model_dump(),
        content_hash=compute_theme_overlay_content_hash(content),
        lineage_hash=compute_theme_overlay_lineage_hash(content),
    )
    malicious_path = archived_path.with_name(
        f"theme-overlay__{document.content_hash}.json"
    )
    malicious_path.write_bytes(canonical_theme_overlay_document_bytes(document))

    observation = reader.governance_repo.read_latest_manifest(
        CHOICE_STOCK_OBSERVATION_CACHE_KEY
    )
    overlay = reader.governance_repo.read_latest_manifest(
        "stock-analysis.theme-overlay.tushare-ths-current"
    )
    assert observation is not None
    assert overlay is not None
    revised_observation = json.loads(json.dumps(observation))
    revised_observation["created_at"] = "2026-07-09T02:00:00Z"
    revised_overlay = json.loads(json.dumps(overlay))
    revised_overlay["lineage"].update(
        {
            "archived_path": str(malicious_path),
            "content_hash": document.content_hash,
            "lineage_hash": document.lineage_hash,
            "observation_anchor": document.observation_anchor.model_dump(mode="json"),
        }
    )
    reader.governance_repo.append(CACHE_MANIFEST_STREAM, revised_observation)
    reader.governance_repo.append(CACHE_MANIFEST_STREAM, revised_overlay)

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 3, tzinfo=UTC),
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_invalid"
    assert result.members == ()


def test_new_observation_revision_invalidates_old_overlay_anchor(
    tmp_path: Path,
) -> None:
    reader, _ = _archive_fixture(tmp_path)
    latest = reader.governance_repo.read_latest_manifest(
        CHOICE_STOCK_OBSERVATION_CACHE_KEY
    )
    assert latest is not None
    revised = dict(latest)
    revised["run_id"] = "choice_stock_refresh:2026-07-08:revision-b"
    revised["source_version"] = "sv_choice_stock_revision_b"
    revised["created_at"] = "2026-07-09T01:30:00Z"
    revised_lineage = dict(revised["lineage"])
    revised_lineage["refresh_run_id"] = revised["run_id"]
    revised["lineage"] = revised_lineage
    reader.governance_repo.append(CACHE_MANIFEST_STREAM, revised)

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_invalid"
    assert result.members == ()


def test_newer_observation_without_matching_overlay_is_quietly_unavailable(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    reader, archived_path = _archive_fixture(tmp_path)
    latest = reader.governance_repo.read_latest_manifest(
        CHOICE_STOCK_OBSERVATION_CACHE_KEY
    )
    assert latest is not None
    newer = dict(latest)
    newer["run_id"] = "choice_stock_refresh:2026-07-14:overlay-off"
    newer["report_date"] = "2026-07-14"
    newer["source_version"] = "sv_choice_stock_20260714"
    newer["vendor_version"] = "vv_choice_stock_20260714"
    newer["created_at"] = "2026-07-14T09:37:13Z"
    newer_lineage = dict(newer["lineage"])
    newer_lineage.update(
        {
            "materialization_run_id": "choice_stock_materialize:2026-07-14:overlay-off",
            "refresh_run_id": newer["run_id"],
            "daily_observation_report_date": "2026-07-14",
        }
    )
    newer["lineage"] = newer_lineage
    reader.governance_repo.append(CACHE_MANIFEST_STREAM, newer)

    # The old archive is unrelated to the newest observation and must not be read.
    archived_path.unlink()
    caplog.set_level(logging.ERROR)

    result = reader.read(
        requested_as_of_date="2026-07-14",
        effective_as_of_date="2026-07-14",
        evaluation_time=datetime(2026, 7, 15, 2, tzinfo=UTC),
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_missing_for_latest_observation"
    assert result.report_date == "2026-07-14"
    assert result.members == ()
    assert "Theme overlay read failed" not in caplog.text


def test_archived_path_escape_fails_closed_without_reading_outside_file(
    tmp_path: Path,
) -> None:
    reader, archived_path = _archive_fixture(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes(archived_path.read_bytes())
    latest = reader.governance_repo.read_latest_manifest(
        "stock-analysis.theme-overlay.tushare-ths-current"
    )
    assert latest is not None
    escaped = dict(latest)
    escaped_lineage = dict(escaped["lineage"])
    escaped_lineage["archived_path"] = str(outside)
    escaped["lineage"] = escaped_lineage
    reader.governance_repo.append(CACHE_MANIFEST_STREAM, escaped)

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_invalid"
    assert result.members == ()


def test_archive_object_symlink_fails_closed(tmp_path: Path) -> None:
    reader, archived_path = _archive_fixture(tmp_path)
    real_path = archived_path.with_name("real-object.json")
    archived_path.replace(real_path)
    try:
        archived_path.symlink_to(real_path)
    except OSError as exc:
        pytest.skip(f"file symlink unavailable: {exc}")

    result = reader.read(
        requested_as_of_date="2026-07-08",
        effective_as_of_date="2026-07-08",
        evaluation_time=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_invalid"
    assert result.members == ()


def test_reader_logs_sensitive_exception_but_returns_only_stable_external_reason(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from backend.app.services import market_data_livermore_service as service

    sensitive_text = "token=secret-value path=C:/private/theme-overlay.json"

    class SensitiveFailureRepo:
        def read_latest_manifest(self, _cache_key: str):
            raise RuntimeError(sensitive_text)

    reader = StockAnalysisThemeOverlayReader(
        archive_root=tmp_path / "archive",
        governance_repo=SensitiveFailureRepo(),  # type: ignore[arg-type]
    )

    with caplog.at_level(
        logging.ERROR,
        logger="backend.app.repositories.stock_analysis_theme_overlay_reader",
    ):
        result = reader.read(
            requested_as_of_date="2026-07-08",
            effective_as_of_date="2026-07-08",
        )

    provenance = service._ThemeBreakoutEvidenceProvenance(
        overlay_status=result.status,
        overlay_reason=result.reason,
    )
    evidence = service._build_theme_breakout_evidence_state(
        stock_readiness=service.choice_stock_readiness_missing("fixture"),
        tables_used=[],
        provenance=provenance,
    )
    external_payload = json.dumps(
        {"reason": result.reason, "evidence": evidence},
        ensure_ascii=False,
    )

    assert result.status == "unavailable"
    assert result.reason == "current_overlay_invalid"
    assert sensitive_text in caplog.text
    assert sensitive_text not in external_payload


def test_archive_byte_change_breaks_fingerprint_even_when_archive_is_invalid(
    tmp_path: Path,
) -> None:
    reader, archived_path = _archive_fixture(tmp_path)
    before = reader.fingerprint()

    archived_path.write_bytes(archived_path.read_bytes() + b"\n")

    assert reader.fingerprint() != before
