from __future__ import annotations

import json
import shutil
import threading
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.repositories import (
    stock_analysis_theme_overlay_archive_repo as theme_archive_repo_module,
)
from backend.app.repositories.governance_repo import (
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import CacheManifestRecord
from backend.app.schemas import stock_analysis_theme_overlay as theme_overlay_schema
from backend.app.tasks.stock_analysis_theme_overlay_archive import (
    CHOICE_STOCK_OBSERVATION_CACHE_KEY,
    THEME_OVERLAY_CACHE_KEY,
    archive_tushare_ths_current_overlay,
)


def _append_observation_manifest(
    governance_dir: Path,
    *,
    report_date: str,
    source_version: str,
    vendor_version: str | None = None,
    run_id: str | None = None,
    created_at: str | None = "2026-07-08T23:00:00Z",
) -> GovernanceRepository:
    repo = GovernanceRepository(base_dir=governance_dir)
    repo.append(
        CACHE_MANIFEST_STREAM,
        CacheManifestRecord(
            cache_key=CHOICE_STOCK_OBSERVATION_CACHE_KEY,
            cache_version="choice_stock_refresh_v1",
            source_version=source_version,
            vendor_version=vendor_version
            or f"vv_choice_stock_{report_date.replace('-', '')}",
            rule_version="rv_choice_stock_materialization_front_layer_v1",
            basis="observational",
            module_name="choice_stock",
            run_id=run_id or f"choice_stock_refresh:{report_date}:fixture",
            report_date=report_date,
            input_sources=["choice_stock_vendor"],
            fact_tables=["choice_stock_daily_observation"],
            created_at=created_at,
        ).model_dump(),
    )
    return repo


def _valid_archive_document():
    anchor = theme_overlay_schema.ThemeOverlayObservationAnchor(
        cache_key=CHOICE_STOCK_OBSERVATION_CACHE_KEY,
        report_date="2026-07-08",
        created_at=datetime(
            2026,
            7,
            9,
            8,
            tzinfo=timezone(timedelta(hours=8)),
        ),
        source_version="sv_choice_stock_latest",
        vendor_version="vv_choice_stock_latest",
        rule_version="rv_choice_stock_materialization_front_layer_v1",
        run_id="choice_stock_refresh:fixture",
    )
    return theme_overlay_schema.build_theme_overlay_archive_document(
        membership_observed_at=datetime(
            2026,
            7,
            9,
            9,
            tzinfo=timezone(timedelta(hours=8)),
        ),
        run_id="theme-overlay:schema-fixture",
        source_version="sv_tushare_ths_fixture",
        vendor_version="vv_tushare_ths_fixture",
        rule_version="rv_stock_analysis_theme_overlay_archive_v1",
        members=(
            theme_overlay_schema.ThemeOverlayMember(
                stock_code="000001.sz",
                stock_name="平安银行",
                theme_key="885002.ti",
                theme_name="金融科技",
            ),
        ),
        observation_anchor=anchor,
    )


def test_archive_current_theme_overlay_uses_latest_landed_manifest_and_governed_object(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    repo = _append_observation_manifest(
        governance_dir,
        report_date="2026-07-07",
        source_version="sv_choice_stock_old",
    )
    _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_dir,
        archive_root=archive_root,
        load_members=lambda: [
            {
                "stock_code": "000002.SZ",
                "stock_name": "万科A",
                "theme_key": "885001.TI",
                "theme_name": "低空经济",
            },
            {
                "stock_code": "000001.SZ",
                "stock_name": "平安银行",
                "theme_key": "885002.TI",
                "theme_name": "金融科技",
            },
        ],
        run_id="theme-overlay:2026-07-08:fixture",
        source_version="sv_tushare_ths_fixture",
        vendor_version="vv_tushare_ths_20260708_fixture",
        membership_observed_at=datetime(2026, 7, 9, 1, 2, 3, tzinfo=UTC),
    )

    assert result.status == "completed"
    assert result.observed_market_date.isoformat() == "2026-07-08"
    assert result.membership_observed_at.isoformat() == "2026-07-09T01:02:03+00:00"
    assert result.member_count == 2
    assert result.manifest_written is True
    assert len(result.content_hash or "") == 64
    assert len(result.lineage_hash or "") == 64

    archived_path = Path(result.archived_path or "")
    assert archived_path.is_file()
    assert archived_path.parent == archive_root / "choice-stock-theme-overlay" / "files"
    assert result.content_hash in archived_path.name

    archived = json.loads(archived_path.read_text(encoding="utf-8"))
    assert archived["source_kind"] == "tushare_ths_current_overlay"
    assert archived["membership_observed_at"] == "2026-07-09T01:02:03Z"
    assert archived["observed_market_date"] == "2026-07-08"
    assert archived["run_id"] == "theme-overlay:2026-07-08:fixture"
    assert archived["source_version"] == "sv_tushare_ths_fixture"
    assert archived["vendor_version"] == "vv_tushare_ths_20260708_fixture"
    assert archived["point_in_time"] is False
    assert archived["historical_use_allowed"] is False
    assert [member["stock_code"] for member in archived["members"]] == [
        "000001.SZ",
        "000002.SZ",
    ]
    assert archived["content_hash"] == result.content_hash
    assert archived["lineage_hash"] == result.lineage_hash
    assert (
        archived["observation_anchor"]["cache_key"]
        == CHOICE_STOCK_OBSERVATION_CACHE_KEY
    )
    assert archived["observation_anchor"]["source_version"] == "sv_choice_stock_latest"

    latest_overlay = repo.read_latest_manifest(THEME_OVERLAY_CACHE_KEY)
    assert latest_overlay is not None
    assert latest_overlay["report_date"] == "2026-07-08"
    assert latest_overlay["fact_tables"] == []
    assert latest_overlay["lineage"]["archived_path"] == str(archived_path)
    assert latest_overlay["lineage"]["point_in_time"] is False
    assert latest_overlay["lineage"]["historical_use_allowed"] is False
    assert latest_overlay["lineage"]["content_hash"] == result.content_hash
    assert latest_overlay["lineage"]["lineage_hash"] == result.lineage_hash


def test_missing_observation_manifest_is_explicit_and_creates_no_directories(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "missing-governance"
    archive_root = tmp_path / "missing-archive"
    loader_called = False

    def load_members() -> list[dict[str, object]]:
        nonlocal loader_called
        loader_called = True
        return []

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_dir,
        archive_root=archive_root,
        load_members=load_members,
        run_id="theme-overlay:missing-anchor",
        source_version="sv_tushare_ths_fixture",
        vendor_version="vv_tushare_ths_fixture",
        membership_observed_at=datetime(2026, 7, 9, tzinfo=UTC),
        dry_run=True,
    )

    assert result.status == "source_unavailable"
    assert result.manifest_written is False
    assert result.archived_path is None
    assert loader_called is False
    assert governance_dir.exists() is False
    assert archive_root.exists() is False


def test_dry_run_is_side_effect_free_and_hashes_canonical_members(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    repo = _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )
    members = [
        {
            "stock_code": "000002.SZ",
            "stock_name": "万科A",
            "theme_key": "885001.TI",
            "theme_name": "低空经济",
        },
        {
            "stock_code": "000001.SZ",
            "stock_name": "平安银行",
            "theme_key": "885002.TI",
            "theme_name": "金融科技",
        },
        {
            "stock_code": "000002.SZ",
            "stock_name": "万科A",
            "theme_key": "885001.TI",
            "theme_name": "低空经济",
        },
    ]
    observed_at = datetime(
        2026,
        7,
        9,
        9,
        2,
        3,
        tzinfo=timezone(timedelta(hours=8)),
    )
    before_rows = repo.read_all(CACHE_MANIFEST_STREAM)

    first = archive_tushare_ths_current_overlay(
        governance_dir=governance_dir,
        archive_root=archive_root,
        load_members=lambda: members,
        run_id="theme-overlay:canonical-fixture",
        source_version="sv_tushare_ths_fixture",
        vendor_version="vv_tushare_ths_fixture",
        membership_observed_at=observed_at,
        dry_run=True,
    )
    second = archive_tushare_ths_current_overlay(
        governance_dir=governance_dir,
        archive_root=archive_root,
        load_members=lambda: list(reversed(members)),
        run_id="theme-overlay:canonical-fixture",
        source_version="sv_tushare_ths_fixture",
        vendor_version="vv_tushare_ths_fixture",
        membership_observed_at=observed_at,
        dry_run=True,
    )

    assert first.status == second.status == "dry_run"
    assert first.member_count == second.member_count == 2
    assert first.membership_observed_at.isoformat() == "2026-07-09T01:02:03+00:00"
    assert first.content_hash == second.content_hash
    assert first.lineage_hash == second.lineage_hash
    assert archive_root.exists() is False
    assert repo.read_all(CACHE_MANIFEST_STREAM) == before_rows


@pytest.mark.parametrize(
    ("member_loader", "expected_status"),
    [
        (lambda: [], "empty_source"),
        (
            lambda: (_ for _ in ()).throw(RuntimeError("vendor unavailable")),
            "source_failed",
        ),
    ],
)
def test_empty_or_failed_source_is_explicit_and_writes_nothing(
    tmp_path: Path,
    member_loader,
    expected_status: str,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    repo = _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )
    before_rows = repo.read_all(CACHE_MANIFEST_STREAM)

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_dir,
        archive_root=archive_root,
        load_members=member_loader,
        run_id=f"theme-overlay:{expected_status}",
        source_version="sv_tushare_ths_fixture",
        vendor_version="vv_tushare_ths_fixture",
        membership_observed_at=datetime(2026, 7, 9, tzinfo=UTC),
    )

    assert result.status == expected_status
    assert result.member_count == 0
    assert result.manifest_written is False
    assert result.archived_path is None
    assert archive_root.exists() is False
    assert repo.read_all(CACHE_MANIFEST_STREAM) == before_rows


def test_membership_observed_at_rejects_naive_datetime_without_writing(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        archive_tushare_ths_current_overlay(
            governance_dir=governance_dir,
            archive_root=archive_root,
            load_members=lambda: [
                {
                    "stock_code": "000001.SZ",
                    "theme_key": "885002.TI",
                    "theme_name": "金融科技",
                }
            ],
            run_id="theme-overlay:naive-time",
            source_version="sv_tushare_ths_fixture",
            vendor_version="vv_tushare_ths_fixture",
            membership_observed_at=datetime(2026, 7, 9),
        )

    assert archive_root.exists() is False


@pytest.mark.parametrize("blank_field", ["run_id", "source_version", "vendor_version"])
def test_required_overlay_lineage_fields_reject_blank_values_before_writing(
    tmp_path: Path,
    blank_field: str,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )
    kwargs = {
        "governance_dir": governance_dir,
        "archive_root": archive_root,
        "load_members": lambda: [
            {
                "stock_code": "000001.SZ",
                "theme_key": "885002.TI",
                "theme_name": "金融科技",
            }
        ],
        "run_id": "theme-overlay:required-fields",
        "source_version": "sv_tushare_ths_fixture",
        "vendor_version": "vv_tushare_ths_fixture",
        "membership_observed_at": datetime(2026, 7, 9, tzinfo=UTC),
    }
    kwargs[blank_field] = "   "

    with pytest.raises(ValueError, match=blank_field):
        archive_tushare_ths_current_overlay(**kwargs)

    assert archive_root.exists() is False


def test_invalid_member_is_source_failed_and_writes_nothing(tmp_path: Path) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_dir,
        archive_root=archive_root,
        load_members=lambda: [
            {
                "stock_code": "000001.SZ",
                "theme_key": "885002.TI",
                "theme_name": "   ",
            }
        ],
        run_id="theme-overlay:invalid-member",
        source_version="sv_tushare_ths_fixture",
        vendor_version="vv_tushare_ths_fixture",
        membership_observed_at=datetime(2026, 7, 9, tzinfo=UTC),
    )

    assert result.status == "source_failed"
    assert archive_root.exists() is False


def test_observation_manifest_after_capture_time_is_source_unavailable(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _append_observation_manifest(
        governance_dir,
        report_date="2026-07-10",
        source_version="sv_choice_stock_future",
    )
    loader_called = False

    def load_members() -> list[dict[str, object]]:
        nonlocal loader_called
        loader_called = True
        return []

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_dir,
        archive_root=archive_root,
        load_members=load_members,
        run_id="theme-overlay:future-anchor",
        source_version="sv_tushare_ths_fixture",
        vendor_version="vv_tushare_ths_fixture",
        membership_observed_at=datetime(2026, 7, 9, 23, 59, tzinfo=UTC),
    )

    assert result.status == "source_unavailable"
    assert "after membership_observed_at" in (result.message or "")
    assert loader_called is False
    assert archive_root.exists() is False


def test_manifest_failure_removes_only_the_new_content_addressed_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )
    members = [
        {
            "stock_code": "000001.SZ",
            "theme_key": "885002.TI",
            "theme_name": "金融科技",
        }
    ]

    def fail_manifest(*_args, **_kwargs):
        raise OSError("manifest write failed")

    monkeypatch.setattr(GovernanceRepository, "append_many_atomic", fail_manifest)
    with pytest.raises(OSError, match="manifest write failed"):
        archive_tushare_ths_current_overlay(
            governance_dir=governance_dir,
            archive_root=archive_root,
            load_members=lambda: members,
            run_id="theme-overlay:new-object-failure",
            source_version="sv_tushare_ths_fixture",
            vendor_version="vv_tushare_ths_fixture",
            membership_observed_at=datetime(2026, 7, 9, tzinfo=UTC),
        )

    assert list(archive_root.rglob("*.json")) == []


def test_manifest_failure_does_not_delete_a_preexisting_same_hash_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )
    kwargs = {
        "governance_dir": governance_dir,
        "archive_root": archive_root,
        "load_members": lambda: [
            {
                "stock_code": "000001.SZ",
                "theme_key": "885002.TI",
                "theme_name": "金融科技",
            }
        ],
        "run_id": "theme-overlay:preexisting-object",
        "source_version": "sv_tushare_ths_fixture",
        "vendor_version": "vv_tushare_ths_fixture",
        "membership_observed_at": datetime(2026, 7, 9, tzinfo=UTC),
    }
    completed = archive_tushare_ths_current_overlay(**kwargs)
    archived_path = Path(completed.archived_path or "")
    original_payload = archived_path.read_bytes()

    def fail_manifest(*_args, **_kwargs):
        raise OSError("manifest write failed")

    monkeypatch.setattr(GovernanceRepository, "append_many_atomic", fail_manifest)
    with pytest.raises(OSError, match="manifest write failed"):
        archive_tushare_ths_current_overlay(**kwargs)

    assert archived_path.read_bytes() == original_payload


def test_same_day_observation_anchor_version_change_gets_distinct_governed_object(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    repo = _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_anchor_a",
        vendor_version="vv_choice_stock_anchor_a",
        run_id="choice_stock_refresh:anchor-a",
        created_at="2026-07-09T00:10:00Z",
    )
    kwargs = {
        "governance_dir": governance_dir,
        "archive_root": archive_root,
        "load_members": lambda: [
            {
                "stock_code": "000001.SZ",
                "theme_key": "885002.TI",
                "theme_name": "金融科技",
            }
        ],
        "run_id": "theme-overlay:same-content",
        "source_version": "sv_tushare_ths_fixture",
        "vendor_version": "vv_tushare_ths_fixture",
        "membership_observed_at": datetime(2026, 7, 9, 1, tzinfo=UTC),
    }
    first = archive_tushare_ths_current_overlay(**kwargs)

    _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_anchor_b",
        vendor_version="vv_choice_stock_anchor_b",
        run_id="choice_stock_refresh:anchor-b",
        created_at="2026-07-09T00:20:00Z",
    )
    second = archive_tushare_ths_current_overlay(**kwargs)

    assert first.status == second.status == "completed"
    assert first.content_hash != second.content_hash
    assert first.lineage_hash != second.lineage_hash
    assert first.archived_path != second.archived_path
    first_document = json.loads(
        Path(first.archived_path or "").read_text(encoding="utf-8")
    )
    second_document = json.loads(
        Path(second.archived_path or "").read_text(encoding="utf-8")
    )
    assert first_document["observation_anchor"]["source_version"] == (
        "sv_choice_stock_anchor_a"
    )
    assert second_document["observation_anchor"]["source_version"] == (
        "sv_choice_stock_anchor_b"
    )
    assert first_document["observation_anchor"]["created_at"] == (
        "2026-07-09T00:10:00Z"
    )
    assert second_document["observation_anchor"]["created_at"] == (
        "2026-07-09T00:20:00Z"
    )

    overlay_manifests = [
        row
        for row in repo.read_all(CACHE_MANIFEST_STREAM)
        if row.get("cache_key") == THEME_OVERLAY_CACHE_KEY
    ]
    assert [row["lineage"]["archived_path"] for row in overlay_manifests] == [
        first.archived_path,
        second.archived_path,
    ]
    assert [
        row["lineage"]["observation_anchor"]["source_version"]
        for row in overlay_manifests
    ] == ["sv_choice_stock_anchor_a", "sv_choice_stock_anchor_b"]


@pytest.mark.parametrize(
    "created_at",
    [
        None,
        "2026-07-09T00:30:00",
        "not-a-timestamp",
        "2026-07-09T01:00:01Z",
    ],
)
def test_untrusted_observation_manifest_created_at_is_source_unavailable_and_writes_nothing(
    tmp_path: Path,
    created_at: str | None,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    repo = _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
        created_at=created_at,
    )
    before_rows = repo.read_all(CACHE_MANIFEST_STREAM)
    loader_called = False

    def load_members() -> list[dict[str, object]]:
        nonlocal loader_called
        loader_called = True
        return []

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_dir,
        archive_root=archive_root,
        load_members=load_members,
        run_id="theme-overlay:invalid-anchor-created-at",
        source_version="sv_tushare_ths_fixture",
        vendor_version="vv_tushare_ths_fixture",
        membership_observed_at=datetime(2026, 7, 9, 1, tzinfo=UTC),
    )

    assert result.status == "source_unavailable"
    assert "created_at" in (result.message or "")
    assert loader_called is False
    assert archive_root.exists() is False
    assert repo.read_all(CACHE_MANIFEST_STREAM) == before_rows


def test_reused_content_addressed_object_must_match_expected_canonical_bytes(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    repo = _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )
    kwargs = {
        "governance_dir": governance_dir,
        "archive_root": archive_root,
        "load_members": lambda: [
            {
                "stock_code": "000001.SZ",
                "theme_key": "885002.TI",
                "theme_name": "金融科技",
            }
        ],
        "run_id": "theme-overlay:tampered-object",
        "source_version": "sv_tushare_ths_fixture",
        "vendor_version": "vv_tushare_ths_fixture",
        "membership_observed_at": datetime(2026, 7, 9, tzinfo=UTC),
    }
    completed = archive_tushare_ths_current_overlay(**kwargs)
    archived_path = Path(completed.archived_path or "")
    manifest_rows_before = repo.read_all(CACHE_MANIFEST_STREAM)
    archived_path.write_bytes(b"{}")

    with pytest.raises(ValueError, match="content-addressed archive mismatch"):
        archive_tushare_ths_current_overlay(**kwargs)

    assert archived_path.read_bytes() == b"{}"
    assert repo.read_all(CACHE_MANIFEST_STREAM) == manifest_rows_before


def test_injected_sql_authority_repo_reads_anchor_without_existing_jsonl_directory(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "sql-shadow-jsonl"
    archive_root = tmp_path / "archive"
    sql_repo = GovernanceRepository(
        base_dir=governance_dir,
        sql_dsn=f"sqlite:///{(tmp_path / 'governance.db').as_posix()}",
        backend_mode="sql-authority",
    )
    sql_repo.append(
        CACHE_MANIFEST_STREAM,
        CacheManifestRecord(
            cache_key=CHOICE_STOCK_OBSERVATION_CACHE_KEY,
            cache_version="choice_stock_refresh_v1",
            source_version="sv_choice_stock_sql",
            vendor_version="vv_choice_stock_sql",
            rule_version="rv_choice_stock_materialization_front_layer_v1",
            basis="observational",
            module_name="choice_stock",
            run_id="choice_stock_refresh:sql-authority",
            report_date="2026-07-08",
            input_sources=["choice_stock_vendor"],
            fact_tables=["choice_stock_daily_observation"],
            created_at="2026-07-08T23:00:00Z",
        ).model_dump(),
    )
    shutil.rmtree(governance_dir)
    assert governance_dir.exists() is False

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_dir,
        governance_repo=sql_repo,
        archive_root=archive_root,
        load_members=lambda: [
            {
                "stock_code": "000001.SZ",
                "theme_key": "885002.TI",
                "theme_name": "金融科技",
            }
        ],
        run_id="theme-overlay:sql-authority",
        source_version="sv_tushare_ths_sql",
        vendor_version="vv_tushare_ths_sql",
        membership_observed_at=datetime(2026, 7, 9, tzinfo=UTC),
    )

    assert result.status == "completed"
    latest = sql_repo.read_latest_manifest(THEME_OVERLAY_CACHE_KEY)
    assert latest is not None
    assert latest["lineage"]["observation_anchor"]["source_version"] == (
        "sv_choice_stock_sql"
    )
    assert (governance_dir / "cache_manifest.jsonl").is_file()


def test_concurrent_same_hash_failed_writer_cannot_delete_success_manifest_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    authoritative_repo = _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )
    success_at_exists = threading.Event()
    success_manifest_written = threading.Event()
    exists_barrier = threading.Barrier(2)
    original_exists = Path.exists

    def coordinated_exists(path: Path) -> bool:
        if path.name.startswith("theme-overlay__"):
            existed = original_exists(path)
            if threading.current_thread().name == "overlay-success":
                success_at_exists.set()
            try:
                exists_barrier.wait(timeout=0.2)
            except threading.BrokenBarrierError:
                pass
            return existed
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", coordinated_exists)

    class CoordinatedRepo:
        def __init__(self, *, should_fail: bool) -> None:
            self.should_fail = should_fail
            self.backend_mode = authoritative_repo.backend_mode
            self.base_dir = authoritative_repo.base_dir
            self.sql_dsn = authoritative_repo.sql_dsn

        def read_latest_manifest(self, cache_key: str):
            return authoritative_repo.read_latest_manifest(cache_key)

        def append_many_atomic(self, entries):
            if self.should_fail:
                assert success_manifest_written.wait(timeout=2)
                raise OSError("coordinated manifest failure")
            paths = authoritative_repo.append_many_atomic(entries)
            success_manifest_written.set()
            return paths

    kwargs = {
        "governance_dir": governance_dir,
        "archive_root": archive_root,
        "load_members": lambda: [
            {
                "stock_code": "000001.SZ",
                "theme_key": "885002.TI",
                "theme_name": "金融科技",
            }
        ],
        "run_id": "theme-overlay:concurrent",
        "source_version": "sv_tushare_ths_fixture",
        "vendor_version": "vv_tushare_ths_fixture",
        "membership_observed_at": datetime(2026, 7, 9, tzinfo=UTC),
    }
    results: list[object] = []
    errors: list[BaseException] = []

    def run(repo: CoordinatedRepo) -> None:
        try:
            results.append(
                archive_tushare_ths_current_overlay(
                    **kwargs,
                    governance_repo=repo,
                )
            )
        except BaseException as exc:
            errors.append(exc)

    success_thread = threading.Thread(
        target=run,
        args=(CoordinatedRepo(should_fail=False),),
        name="overlay-success",
    )
    failed_thread = threading.Thread(
        target=run,
        args=(CoordinatedRepo(should_fail=True),),
        name="overlay-failed",
    )
    success_thread.start()
    assert success_at_exists.wait(timeout=2)
    failed_thread.start()
    success_thread.join(timeout=5)
    failed_thread.join(timeout=5)

    assert success_thread.is_alive() is False
    assert failed_thread.is_alive() is False
    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], OSError)
    latest = authoritative_repo.read_latest_manifest(THEME_OVERLAY_CACHE_KEY)
    assert latest is not None
    target = Path(str(latest["lineage"]["archived_path"]))
    assert target.is_file()


def test_archive_schema_is_frozen_utc_and_rejects_noncanonical_hashes() -> None:
    document = _valid_archive_document()

    assert document.membership_observed_at.isoformat() == "2026-07-09T01:00:00+00:00"
    assert document.observation_anchor.created_at.isoformat() == (
        "2026-07-09T00:00:00+00:00"
    )
    assert isinstance(document.members, tuple)
    assert document.members[0].stock_code == "000001.SZ"
    assert document.members[0].theme_key == "885002.TI"
    assert len(document.content_hash) == 64
    assert len(document.lineage_hash) == 64

    with pytest.raises(ValidationError, match="frozen"):
        document.members[0].stock_code = "000002.SZ"
    with pytest.raises(ValidationError, match="frozen"):
        document.members = ()

    invalid_content_hash = document.model_dump()
    invalid_content_hash["content_hash"] = "A" * 64
    with pytest.raises(ValidationError, match="content_hash"):
        theme_overlay_schema.ThemeOverlayArchiveDocument.model_validate(
            invalid_content_hash
        )
    invalid_lineage_hash = document.model_dump()
    invalid_lineage_hash["lineage_hash"] = "0" * 63
    with pytest.raises(ValidationError, match="lineage_hash"):
        theme_overlay_schema.ThemeOverlayArchiveDocument.model_validate(
            invalid_lineage_hash
        )

    with pytest.raises(ValidationError, match="timezone"):
        theme_overlay_schema.ThemeOverlayObservationAnchor(
            cache_key=CHOICE_STOCK_OBSERVATION_CACHE_KEY,
            report_date="2026-07-08",
            created_at=datetime(2026, 7, 9),
            source_version="sv_choice_stock_latest",
            vendor_version="vv_choice_stock_latest",
            rule_version="rv_choice_stock_materialization_front_layer_v1",
        )


@pytest.mark.parametrize("stale_field", ["content_hash", "lineage_hash"])
def test_repository_recomputes_and_rejects_stale_document_hashes_before_write(
    tmp_path: Path,
    stale_field: str,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    governance_repo = _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )
    rows_before = governance_repo.read_all(CACHE_MANIFEST_STREAM)
    document = _valid_archive_document().model_copy(update={stale_field: "0" * 64})
    repository = theme_archive_repo_module.StockAnalysisThemeOverlayArchiveRepository(
        archive_root=archive_root,
        governance_repo=governance_repo,
    )

    with pytest.raises(ValueError, match=f"{stale_field} mismatch"):
        repository.archive(
            document=document,
            manifest_payload=CacheManifestRecord(
                cache_key=THEME_OVERLAY_CACHE_KEY,
                source_version="sv_tushare_ths_fixture",
                vendor_version="vv_tushare_ths_fixture",
                rule_version="rv_stock_analysis_theme_overlay_archive_v1",
            ).model_dump(),
        )

    assert list(archive_root.rglob("*.json")) == []
    assert governance_repo.read_all(CACHE_MANIFEST_STREAM) == rows_before


def test_repository_rejects_files_directory_symlink_escape(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    outside = tmp_path / "outside"
    governance_repo = _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )
    rows_before = governance_repo.read_all(CACHE_MANIFEST_STREAM)
    files_parent = archive_root / "choice-stock-theme-overlay"
    files_parent.mkdir(parents=True)
    outside.mkdir()
    try:
        (files_parent / "files").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")
    repository = theme_archive_repo_module.StockAnalysisThemeOverlayArchiveRepository(
        archive_root=archive_root,
        governance_repo=governance_repo,
    )

    with pytest.raises(ValueError, match="symlink|escapes archive root"):
        repository.archive(
            document=_valid_archive_document(),
            manifest_payload=CacheManifestRecord(
                cache_key=THEME_OVERLAY_CACHE_KEY,
                source_version="sv_tushare_ths_fixture",
                vendor_version="vv_tushare_ths_fixture",
                rule_version="rv_stock_analysis_theme_overlay_archive_v1",
            ).model_dump(),
        )

    assert list(outside.glob("*.json")) == []
    assert governance_repo.read_all(CACHE_MANIFEST_STREAM) == rows_before


def test_canonical_members_merge_case_and_empty_labels_but_keep_distinct_themes(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_dir,
        archive_root=archive_root,
        load_members=lambda: [
            {
                "stock_code": "000001.sz",
                "stock_name": "",
                "theme_key": "885002.ti",
                "theme_name": "",
            },
            {
                "stock_code": "000001.SZ",
                "stock_name": "平安银行",
                "theme_key": "885002.TI",
                "theme_name": "金融科技",
            },
            {
                "stock_code": "000001.sz",
                "stock_name": "平安银行",
                "theme_key": "885003.ti",
                "theme_name": "跨境支付",
            },
        ],
        run_id="theme-overlay:canonical-members",
        source_version="sv_tushare_ths_fixture",
        vendor_version="vv_tushare_ths_fixture",
        membership_observed_at=datetime(2026, 7, 9, tzinfo=UTC),
    )

    assert result.status == "completed"
    assert result.member_count == 2
    document = json.loads(Path(result.archived_path or "").read_text(encoding="utf-8"))
    assert [
        (member["stock_code"], member["theme_key"], member["theme_name"])
        for member in document["members"]
    ] == [
        ("000001.SZ", "885002.TI", "金融科技"),
        ("000001.SZ", "885003.TI", "跨境支付"),
    ]


@pytest.mark.parametrize(
    ("conflicting_field", "first_value", "second_value"),
    [
        ("stock_name", "平安银行", "平安银行股份"),
        ("theme_name", "金融科技", "数字金融"),
    ],
)
def test_canonical_member_label_conflict_is_source_failed_without_writes(
    tmp_path: Path,
    conflicting_field: str,
    first_value: str,
    second_value: str,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    governance_repo = _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )
    rows_before = governance_repo.read_all(CACHE_MANIFEST_STREAM)
    first = {
        "stock_code": "000001.sz",
        "stock_name": "平安银行",
        "theme_key": "885002.ti",
        "theme_name": "金融科技",
    }
    second = dict(first)
    first[conflicting_field] = first_value
    second[conflicting_field] = second_value

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_dir,
        archive_root=archive_root,
        load_members=lambda: [first, second],
        run_id="theme-overlay:conflicting-member-label",
        source_version="sv_tushare_ths_fixture",
        vendor_version="vv_tushare_ths_fixture",
        membership_observed_at=datetime(2026, 7, 9, tzinfo=UTC),
    )

    assert result.status == "source_failed"
    assert conflicting_field in (result.message or "")
    assert archive_root.exists() is False
    assert governance_repo.read_all(CACHE_MANIFEST_STREAM) == rows_before


def test_content_hash_candidate_symlink_alias_is_rejected_even_with_matching_bytes(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    governance_repo = _append_observation_manifest(
        governance_dir,
        report_date="2026-07-08",
        source_version="sv_choice_stock_latest",
    )
    rows_before = governance_repo.read_all(CACHE_MANIFEST_STREAM)
    document = _valid_archive_document()
    files_dir = archive_root / "choice-stock-theme-overlay" / "files"
    files_dir.mkdir(parents=True)
    real_object = files_dir / "same-bytes-real-object.json"
    real_object.write_bytes(
        theme_overlay_schema.canonical_theme_overlay_document_bytes(document)
    )
    candidate = files_dir / f"theme-overlay__{document.content_hash}.json"
    try:
        candidate.symlink_to(real_object)
    except OSError as exc:
        pytest.skip(f"file symlink unavailable: {exc}")
    repository = theme_archive_repo_module.StockAnalysisThemeOverlayArchiveRepository(
        archive_root=archive_root,
        governance_repo=governance_repo,
    )

    with pytest.raises(ValueError, match="symlink"):
        repository.archive(
            document=document,
            manifest_payload=CacheManifestRecord(
                cache_key=THEME_OVERLAY_CACHE_KEY,
                source_version="sv_tushare_ths_fixture",
                vendor_version="vv_tushare_ths_fixture",
                rule_version="rv_stock_analysis_theme_overlay_archive_v1",
            ).model_dump(),
        )

    assert candidate.is_symlink()
    assert governance_repo.read_all(CACHE_MANIFEST_STREAM) == rows_before
