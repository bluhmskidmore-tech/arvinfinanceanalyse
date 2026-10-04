from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from decimal import Decimal
from importlib import import_module
from pathlib import Path

import duckdb
import pytest

from backend.app.repositories.pnl_precompute_state import (
    PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
    PnlByBusinessPrecomputeStaleWriteError,
    invalidate_pnl_by_business_precompute_on_connection,
    required_pnl_by_business_revision_on_connection,
)
from backend.app.repositories.pnl_repo import (
    PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
    PnlRepository,
)
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.tasks import pnl_by_business_precompute
from backend.app.tasks import pnl_by_business_resource_scope


def _create_precompute_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table fact_pnl_by_business_precompute (
            year integer, as_of_date varchar, result_kind varchar,
            dimension varchar, business_key varchar, payload_json varchar,
            source_version varchar, rule_version varchar, generated_at timestamp
        )
        """
    )


def _record(*, source_version: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "year": 2025,
        "as_of_date": "2025-06-30",
        "result_kind": "monthly",
        "dimension": "",
        "business_key": "",
        "payload_json": json.dumps(payload),
        "source_version": source_version,
        "rule_version": PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        "generated_at": "2026-09-13T00:00:00+00:00",
    }


def test_invalidation_is_atomic_and_preserves_known_cutoffs(tmp_path) -> None:
    duckdb_path = tmp_path / "state.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        _create_precompute_table(conn)
        conn.executemany(
            """
            insert into fact_pnl_by_business_precompute values
                (?, ?, 'monthly', '', '', '{}', 'legacy', 'legacy', current_timestamp)
            """,
            [(2025, "2025-03-31"), (2025, "2025-06-30"), (2026, "2026-06-30")],
        )
        conn.execute("begin transaction")
        receipt = invalidate_pnl_by_business_precompute_on_connection(
            conn,
            changed_report_dates=("2025-04-30", "2026-02-28"),
            reason="fact_replace",
            supported_cutoffs=("2025-04-30", "2026-02-28"),
        )
        assert receipt == {
            "event_revision": 1,
            "affected_years": (2025, 2026),
            "pending_cutoffs": ("2025-04-30", "2025-06-30", "2026-02-28", "2026-06-30"),
        }
        conn.execute("rollback")
        state_table_count = conn.execute(
            """
            select count(*) from information_schema.tables
            where table_name = 'fact_pnl_by_business_precompute_cutoff_state'
            """
        ).fetchone()
        assert state_table_count == (0,)

        conn.execute("begin transaction")
        invalidate_pnl_by_business_precompute_on_connection(
            conn,
            changed_report_dates=("2025-04-30", "2026-02-28"),
            reason="fact_replace",
            supported_cutoffs=("2025-04-30", "2026-02-28"),
        )
        conn.execute("commit")
    finally:
        conn.close()

    repo = PnlRepository(str(duckdb_path))
    pending = repo.list_pending_pnl_by_business_precompute()
    assert [(item["year"], item["target_dates"]) for item in pending] == [
        (2025, ("2025-03-31",)),
        (2025, ("2025-04-30", "2025-06-30")),
        (2026, ("2026-02-28", "2026-06-30")),
    ]
    assert [item["dependency_revision"] for item in pending] == [0, 1, 1]
    assert pending[0]["reason"] == "protocol_upgrade"


def test_separate_purge_and_insert_commits_advance_revision_twice(tmp_path) -> None:
    duckdb_path = tmp_path / "two-commits.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("begin transaction")
        first = invalidate_pnl_by_business_precompute_on_connection(
            conn,
            changed_report_dates=("2025-06-30",),
            reason="fact_purge",
            supported_cutoffs=("2025-06-30",),
        )
        conn.execute("commit")
        conn.execute("begin transaction")
        second = invalidate_pnl_by_business_precompute_on_connection(
            conn,
            changed_report_dates=("2025-06-30",),
            reason="fact_insert",
            supported_cutoffs=("2025-06-30",),
        )
        conn.execute("commit")
        required = required_pnl_by_business_revision_on_connection(
            conn,
            year=2025,
            as_of_date="2025-06-30",
        )
    finally:
        conn.close()
    assert first["event_revision"] == 1
    assert second["event_revision"] == 2
    assert required == 2


def test_daily_change_without_known_cutoff_keeps_dirty_range_only(tmp_path) -> None:
    duckdb_path = tmp_path / "daily-dirty.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("begin transaction")
        receipt = invalidate_pnl_by_business_precompute_on_connection(
            conn,
            changed_report_dates=("2025-06-17",),
            reason="daily_balance_replace",
        )
        conn.execute("commit")
    finally:
        conn.close()
    assert receipt["pending_cutoffs"] == ()
    pending = PnlRepository(str(duckdb_path)).list_pending_pnl_by_business_precompute()
    assert len(pending) == 1
    assert pending[0] == {
        "year": 2025,
        "dependency_revision": 1,
        "dirty_from_date": "2025-06-17",
        "target_dates": (),
        "reason": "daily_balance_replace",
        "invalidated_at": pending[0]["invalidated_at"],
        "protocol_version": PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
    }
    assert pending[0]["invalidated_at"]


def test_queued_build_rejects_obsolete_revision_before_fact_reads(monkeypatch) -> None:
    class FakeRepository:
        def __init__(self, _path: str) -> None:
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap == "2025-06-30"
            return "2025-06-30"

        def pnl_by_business_precompute_dependency_revision(self, *, year, as_of_date):
            assert (year, as_of_date) == (2025, "2025-06-30")
            return 3

        def require_current_formal_pnl_rule_version(self, **_kwargs):
            raise AssertionError("obsolete build must fail before source reads")

    monkeypatch.setattr(pnl_by_business_precompute, "PnlRepository", FakeRepository)
    with pytest.raises(PnlByBusinessPrecomputeStaleWriteError, match="expected revision 2"):
        pnl_by_business_precompute.precompute_pnl_by_business_payloads(
            duckdb_path="unused.duckdb",
            governance_dir="unused-governance",
            year=2025,
            as_of_date="2025-06-30",
            expected_dependency_revision=2,
        )


def test_ytd_builder_receives_same_ftp_and_adjustment_snapshot(monkeypatch) -> None:
    pnl_service = import_module("backend.app.services.pnl_service")

    approved_adjustments = [{"adjustment_id": "adj-1", "report_date": "2025-06-30"}]
    received: dict[str, object] = {}
    expected_payload = object()

    def fake_builder(**kwargs):
        received.update(kwargs)
        return expected_payload, "2025-06-30"

    monkeypatch.setattr(
        pnl_service,
        "_pnl_by_business_ytd_payload_from_formal_facts",
        fake_builder,
    )
    result = pnl_by_business_precompute._build_pnl_by_business_ytd_payload_for_precompute(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        year=2025,
        as_of_date="2025-06-30",
        ftp_rate_pct=Decimal("1.60"),
        approved_adjustments=approved_adjustments,
    )

    assert result is expected_payload
    assert received["ftp_rate_pct"] == Decimal("1.60")
    assert received["approved_adjustments"] is approved_adjustments


def test_ytd_builder_uses_the_precompute_scoped_business_match_cache(monkeypatch) -> None:
    pnl_service = import_module("backend.app.services.pnl_service")
    calls: list[dict[str, object]] = []
    expected_payload = object()

    def match(classification):
        calls.append(classification)
        return ({"row_key": "asset_zqtz_policy_financial_bond"},)

    def fake_builder(**kwargs):
        matcher = kwargs["business_row_matcher"]
        first = {"report_date": "2026-07-31", "instrument_code": "BOND-1"}
        next_date = {"report_date": "2026-08-31", "instrument_code": "BOND-1"}
        assert matcher(first) == matcher(next_date)
        return expected_payload, "2026-08-31"

    monkeypatch.setattr(pnl_by_business_precompute, "match_zqtz_asset_bond_rows", match)
    monkeypatch.setattr(
        pnl_service,
        "_pnl_by_business_ytd_payload_from_formal_facts",
        fake_builder,
    )

    result = pnl_by_business_precompute._build_pnl_by_business_ytd_payload_for_precompute(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        year=2026,
        as_of_date="2026-08-31",
        business_match_cache={},
    )

    assert result is expected_payload
    assert len(calls) == 1


def test_formal_ytd_builder_uses_and_forwards_injected_business_matcher(monkeypatch) -> None:
    pnl_service = import_module("backend.app.services.pnl_service")
    row_def = dict(pnl_service.ZQTZ_ASSET_BOND_ROWS[0])
    matcher_calls: list[dict[str, object]] = []
    forwarded: dict[str, object] = {}
    expected_payload = object()

    class FakeRepository:
        def __init__(self, _path: str) -> None:
            pass

        def list_union_report_dates(self):
            return ["2026-01-31"]

        def fetch_by_business_analysis_pnl_rows(self, **_kwargs):
            return [
                {
                    "report_date": "2026-01-31",
                    "instrument_code": "BOND-1",
                    "interest_income_514": Decimal("0"),
                    "fair_value_change_516": Decimal("0"),
                    "capital_gain_517": Decimal("0"),
                    "manual_adjustment": Decimal("0"),
                    "total_pnl": Decimal("0"),
                }
            ]

        def fetch_by_business_analysis_balance_rows(self, **_kwargs):
            return []

    def injected_matcher(classification):
        matcher_calls.append(classification)
        return (row_def,)

    def fake_payload_builder(**kwargs):
        forwarded.update(kwargs)
        return expected_payload

    monkeypatch.setattr(pnl_service, "_ensure_formal_pnl_storage_available", lambda _path: None)
    monkeypatch.setattr(pnl_service, "PnlRepository", FakeRepository)
    monkeypatch.setattr(
        pnl_service,
        "match_zqtz_asset_bond_rows",
        lambda _classification: pytest.fail("injected matcher must replace the global matcher"),
    )
    monkeypatch.setattr(
        pnl_service,
        "_analysis_classification_for_pnl_row",
        lambda **_kwargs: {"instrument_code": "BOND-1", "currency_code": "CNY"},
    )
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_by_business_ytd_payload_from_groups",
        fake_payload_builder,
    )

    payload, report_date = pnl_service._pnl_by_business_ytd_payload_from_formal_facts(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        year=2026,
        as_of_date="2026-01-31",
        ftp_rate_pct=Decimal("1.60"),
        approved_adjustments=[],
        business_row_matcher=injected_matcher,
    )

    assert payload is expected_payload
    assert report_date == "2026-01-31"
    assert forwarded["business_row_matcher"] is injected_matcher
    balance_row = {
        "report_date": "2026-01-31",
        "instrument_code": "BOND-1",
        "currency_code": "CNY",
        "avg_amount": Decimal("0"),
        "current_amount": Decimal("0"),
    }
    pnl_service._ytd_business_balance_rows_by_key(
        [balance_row],
        period_end="2026-01-31",
        business_row_matcher=injected_matcher,
    )
    pnl_service._ytd_business_balance_amounts(
        [balance_row],
        period_end="2026-01-31",
        business_row_matcher=injected_matcher,
    )
    assert len(matcher_calls) == 3


def test_ytd_group_builder_forwards_injected_matcher_to_balance_aggregates(monkeypatch) -> None:
    pnl_service = import_module("backend.app.services.pnl_service")
    seen: list[object] = []

    def injected_matcher(_classification):
        return ()

    def rows_by_key(_rows, *, period_end, business_row_matcher=None):
        assert period_end == "2026-01-31"
        seen.append(business_row_matcher)
        return {}

    def amounts(_rows, *, period_end, business_row_matcher=None, unavailable_keys=None):
        assert period_end == "2026-01-31"
        assert unavailable_keys == set()
        seen.append(business_row_matcher)
        return {}, {}

    monkeypatch.setattr(pnl_service, "_ytd_business_balance_rows_by_key", rows_by_key)
    monkeypatch.setattr(pnl_service, "_ytd_business_balance_amounts", amounts)

    pnl_service._build_pnl_by_business_ytd_payload_from_groups(
        year=2026,
        loaded_dates=["2026-01-31"],
        total_pnl=Decimal("0"),
        groups={},
        duckdb_path="unused.duckdb",
        source_tables=[],
        ftp_rate_pct=Decimal("1.60"),
        balance_rows=[],
        business_row_matcher=injected_matcher,
    )

    assert seen == [injected_matcher, injected_matcher]


def test_business_match_cache_reuses_equivalent_classification_across_report_dates(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    expected = ({"row_key": "asset_zqtz_policy_financial_bond"},)

    def match(classification):
        calls.append(classification)
        return expected

    monkeypatch.setattr(pnl_by_business_precompute, "match_zqtz_asset_bond_rows", match)
    cache = {}
    first: dict[str, object] = {
        "report_date": "2026-07-31",
        "instrument_code": "BOND-1",
        "instrument_name": "Bond One",
        "asset_class": "bond",
        "bond_type": "policy",
        "sub_type": "policy",
        "business_type_primary": "policy",
        "business_type_final": "policy",
        "accounting_basis": "AC",
        "currency_code": "CNY",
        "unrelated_field": "first",
    }
    next_date = dict(first, report_date="2026-08-31", unrelated_field="second")

    assert pnl_by_business_precompute._analysis_matched_business_keys(
        first,
        business_match_cache=cache,
    ) == ("asset_zqtz_policy_financial_bond",)
    assert pnl_by_business_precompute._analysis_matched_business_keys(
        next_date,
        business_match_cache=cache,
    ) == ("asset_zqtz_policy_financial_bond",)
    assert len(calls) == 1

    for index, field in enumerate(pnl_by_business_precompute._BUSINESS_MATCH_FIELDS, start=2):
        changed_business_field = dict(next_date, **{field: f"changed-{field}"})
        pnl_by_business_precompute._analysis_matched_business_keys(
            changed_business_field,
            business_match_cache=cache,
        )
        assert len(calls) == index


def test_business_match_cache_key_preserves_matcher_value_normalization() -> None:
    key = pnl_by_business_precompute._analysis_business_match_cache_key

    assert key({}) == key({"instrument_code": None, "currency_code": "  "})
    assert key({"instrument_code": Decimal("0")}) != key({"instrument_code": None})
    assert key({"instrument_code": 0}) != key({"instrument_code": None})
    assert key({"instrument_code": False}) != key({"instrument_code": None})


def test_business_match_cache_fields_cover_matcher_row_reads() -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "app"
        / "core_finance"
        / "zqtz_asset_bond_category.py"
    )
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    pending = ["match_zqtz_asset_bond_rows"]
    visited: set[str] = set()
    row_fields: set[str] = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        function = functions[name]
        first_parameter = function.args.args[0].arg if function.args.args else ""
        local_string_sequences: dict[str, set[str]] = {}
        for node in ast.walk(function):
            if not (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, (ast.Tuple, ast.List, ast.Set))
            ):
                continue
            values = {
                item.value
                for item in node.value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            }
            local_string_sequences[node.targets[0].id] = values
        for node in ast.walk(function):
            if (
                isinstance(node, ast.For)
                and isinstance(node.target, ast.Name)
                and isinstance(node.iter, ast.Name)
            ):
                local_string_sequences[node.target.id] = local_string_sequences.get(
                    node.iter.id,
                    set(),
                )
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in functions and node.func.id not in visited:
                    pending.append(node.func.id)
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == first_parameter
                and node.args
            ):
                continue
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                row_fields.add(argument.value)
            elif isinstance(argument, ast.Name):
                row_fields.update(local_string_sequences.get(argument.id, set()))

    assert row_fields == set(pnl_by_business_precompute._BUSINESS_MATCH_FIELDS)


def test_stale_build_cannot_replace_existing_result(tmp_path) -> None:
    duckdb_path = tmp_path / "stale-write.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        _create_precompute_table(conn)
        conn.execute(
            """
            insert into fact_pnl_by_business_precompute values
                (2025, '2025-06-30', 'monthly', '', '', '{"old": true}',
                 'legacy', 'legacy', current_timestamp)
            """
        )
        conn.execute("begin transaction")
        invalidate_pnl_by_business_precompute_on_connection(
            conn,
            changed_report_dates=("2025-03-31",),
            reason="fact_replace",
        )
        conn.execute("commit")
    finally:
        conn.close()

    repo = PnlRepository(str(duckdb_path))
    source_version = repo.pnl_by_business_precompute_source_version(
        year=2025,
        as_of_date="2025-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
    )
    with repository_task_write_scope("backend.app.tasks.test_pnl_by_business_precompute_state"):
        with pytest.raises(PnlByBusinessPrecomputeStaleWriteError):
            repo.replace_pnl_by_business_precompute(
                year=2025,
                as_of_date="2025-06-30",
                records=[_record(source_version=source_version, payload={"new": True})],
                expected_dependency_revision=0,
                effective_ftp_rate_pct=Decimal("1.60"),
            )
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        payload = conn.execute(
            "select payload_json from fact_pnl_by_business_precompute"
        ).fetchone()
    finally:
        conn.close()
    assert payload == ('{"old": true}',)


def test_complete_source_hash_is_rechecked_before_replace(tmp_path) -> None:
    duckdb_path = tmp_path / "source-race.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        _create_precompute_table(conn)
        conn.execute(
            """
            create table fact_formal_pnl_fi (
                report_date varchar,
                instrument_code varchar,
                portfolio_name varchar,
                cost_center varchar,
                accounting_basis varchar,
                currency_basis varchar,
                interest_income_514 decimal(24, 8),
                fair_value_change_516 decimal(24, 8),
                capital_gain_517 decimal(24, 8),
                manual_adjustment decimal(24, 8),
                total_pnl decimal(24, 8),
                rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
                ('2025-06-30', 'BOND-1', 'BOOK-1', 'CC-1', 'AC', 'CNY',
                 100, 0, 0, 0, 100, 'rule-v1')
            """
        )
        conn.execute(
            """
            insert into fact_pnl_by_business_precompute values
                (2025, '2025-06-30', 'monthly', '', '', '{"old": true}',
                 'legacy', 'legacy', current_timestamp)
            """
        )
    finally:
        conn.close()
    repo = PnlRepository(str(duckdb_path))
    source_version = repo.pnl_by_business_precompute_source_version(
        year=2025,
        as_of_date="2025-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("update fact_formal_pnl_fi set total_pnl = 101")
    finally:
        conn.close()

    with repository_task_write_scope("backend.app.tasks.test_pnl_by_business_precompute_state"):
        with pytest.raises(PnlByBusinessPrecomputeStaleWriteError, match="source facts changed"):
            repo.replace_pnl_by_business_precompute(
                year=2025,
                as_of_date="2025-06-30",
                records=[_record(source_version=source_version, payload={"new": True})],
                expected_dependency_revision=0,
                effective_ftp_rate_pct=Decimal("1.60"),
            )
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        payload = conn.execute(
            "select payload_json from fact_pnl_by_business_precompute"
        ).fetchone()
    finally:
        conn.close()
    assert payload == ('{"old": true}',)


def test_trusted_read_requires_new_protocol_and_lightweight_snapshot_match(tmp_path) -> None:
    duckdb_path = tmp_path / "trusted-read.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        _create_precompute_table(conn)
        conn.execute(
            """
            insert into fact_pnl_by_business_precompute values
                (2025, '2025-06-30', 'monthly', '', '', '{"legacy": true}',
                 'legacy', ?, current_timestamp)
            """,
            [PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION],
        )
    finally:
        conn.close()

    repo = PnlRepository(str(duckdb_path))
    assert repo.fetch_trusted_pnl_by_business_precompute(
        year=2025,
        as_of_date="2025-06-30",
        result_kind="monthly",
        dimension="",
        business_key="",
        effective_ftp_rate_pct=Decimal("1.60"),
    ) is None
    assert repo.list_pending_pnl_by_business_precompute() == [
        {
            "year": 2025,
            "dependency_revision": 0,
            "dirty_from_date": "2025-06-30",
            "target_dates": ("2025-06-30",),
            "reason": "protocol_upgrade",
            "invalidated_at": None,
            "protocol_version": PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
        }
    ]

    source_version = repo.pnl_by_business_precompute_source_version(
        year=2025,
        as_of_date="2025-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
        supplemental_source_version="adjustments:v1",
    )
    with repository_task_write_scope("backend.app.tasks.test_pnl_by_business_precompute_state"):
        repo.replace_pnl_by_business_precompute(
            year=2025,
            as_of_date="2025-06-30",
            records=[_record(source_version=source_version, payload={"ready": True})],
            expected_dependency_revision=0,
            effective_ftp_rate_pct=Decimal("1.6000"),
            supplemental_source_version="adjustments:v1",
        )

    assert repo.fetch_trusted_pnl_by_business_precompute(
        year=2025,
        as_of_date="2025-06-30",
        result_kind="monthly",
        dimension="",
        business_key="",
        effective_ftp_rate_pct=Decimal("1.60"),
        supplemental_source_version="adjustments:v1",
    ) == {"ready": True}
    state = repo.fetch_pnl_by_business_precompute_state(
        year=2025,
        as_of_date="2025-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
        supplemental_source_version="adjustments:v1",
    )
    assert state is not None
    assert state["protocol_version"] == PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION
    assert state["is_ready"] is True
    assert repo.fetch_trusted_pnl_by_business_precompute(
        year=2025,
        as_of_date="2025-06-30",
        result_kind="monthly",
        dimension="",
        business_key="",
        effective_ftp_rate_pct=Decimal("1.61"),
        supplemental_source_version="adjustments:v1",
    ) is None


def test_unrelated_year_and_later_change_do_not_stale_earlier_cutoff(tmp_path) -> None:
    duckdb_path = tmp_path / "scoped-revision.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        _create_precompute_table(conn)
    finally:
        conn.close()
    repo = PnlRepository(str(duckdb_path))
    source_version = repo.pnl_by_business_precompute_source_version(
        year=2025,
        as_of_date="2025-03-31",
        effective_ftp_rate_pct=Decimal("1.60"),
    )
    record = _record(source_version=source_version, payload={"ready": True})
    record["as_of_date"] = "2025-03-31"
    with repository_task_write_scope("backend.app.tasks.test_pnl_by_business_precompute_state"):
        repo.replace_pnl_by_business_precompute(
            year=2025,
            as_of_date="2025-03-31",
            records=[record],
            expected_dependency_revision=0,
            effective_ftp_rate_pct=Decimal("1.60"),
        )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("begin transaction")
        invalidate_pnl_by_business_precompute_on_connection(
            conn,
            changed_report_dates=("2026-01-31",),
            reason="other_year",
        )
        conn.execute("commit")
        conn.execute("begin transaction")
        invalidate_pnl_by_business_precompute_on_connection(
            conn,
            changed_report_dates=("2025-04-30",),
            reason="later_cutoff",
        )
        conn.execute("commit")
    finally:
        conn.close()
    assert repo.fetch_trusted_pnl_by_business_precompute(
        year=2025,
        as_of_date="2025-03-31",
        result_kind="monthly",
        dimension="",
        business_key="",
        effective_ftp_rate_pct=Decimal("1.60"),
    ) == {"ready": True}


def test_bounded_resource_profile_applies_to_read_and_write_connections(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "bounded.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.close()
    monkeypatch.setattr(pnl_by_business_precompute.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(
        pnl_by_business_precompute,
        "_physical_memory_bytes",
        lambda: 32 * 1024**3,
    )

    budget = pnl_by_business_precompute._PnlByBusinessDuckdbResourceBudget(
        str(duckdb_path)
    )
    with budget:
        read_conn = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            assert read_conn.execute(
                "select current_setting('threads')"
            ).fetchone() == (8,)
        finally:
            read_conn.close()

        budget.enter_write_phase()
        write_conn = duckdb.connect(str(duckdb_path), read_only=False)
        try:
            assert write_conn.execute(
                "select current_setting('threads')"
            ).fetchone() == (8,)
        finally:
            write_conn.close()

    assert [item["access_mode"] for item in budget.observations] == [
        "read_only",
        "read_only",
        "read_write",
        "read_write",
    ]
    assert all(item["threads"] == 8 for item in budget.observations)
    assert all(
        0 < item["memory_limit_bytes"] <= int(Decimal(32 * 1024**3) * Decimal("0.30"))
        for item in budget.observations
    )


def test_process_tree_sampler_includes_worker_child_rss() -> None:
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time; blob=bytearray(8*1024*1024); print('ready', flush=True); time.sleep(5)",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "ready"
        rss_bytes, process_ids = pnl_by_business_resource_scope._process_tree_rss_bytes(
            os.getpid()
        )
        assert child.pid in process_ids
        assert rss_bytes > 8 * 1024**2
    finally:
        child.terminate()
        child.wait(timeout=5)


def test_process_memory_budget_latches_first_breach_and_notifies_once(
    tmp_path, monkeypatch
) -> None:
    samples = iter(((100, (11,)), (500, (11, 12)), (100, (11,))))
    monkeypatch.setattr(
        pnl_by_business_resource_scope,
        "_process_tree_rss_bytes",
        lambda _root_pid: next(samples),
    )
    persisted: list[dict[str, object]] = []
    scope = pnl_by_business_resource_scope.PnlByBusinessTaskResourceScope(
        tmp_path / "unused.duckdb",
        scope_name="test",
        physical_memory=1000,
        process_root_pid=11,
        sample_interval_seconds=60,
        on_budget_exceeded=persisted.append,
    )

    with pytest.raises(
        pnl_by_business_resource_scope.PnlByBusinessResourceBudgetExceeded
    ) as exc_info:
        with scope:
            scope.assert_within_budget("first_breach")

    assert len(persisted) == 1
    assert persisted[0]["exceeded_process_memory_sample"]["rss_bytes"] == 500
    assert exc_info.value.receipt["exceeded_process_memory_sample"]["process_ids"] == [
        11,
        12,
    ]


def test_resource_failure_latch_survives_later_running_record(tmp_path) -> None:
    governance = GovernanceRepository(base_dir=tmp_path)
    failed = {
        "run_id": "bounded-run",
        "job_name": "pnl_by_business_precompute",
        "status": "failed",
        "failure_category": "resource_over_budget",
        "resource_limits": {"profile": "bounded_v1"},
    }
    governance.append(CACHE_BUILD_RUN_STREAM, failed)
    governance.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "bounded-run",
            "job_name": "pnl_by_business_precompute",
            "status": "running",
        },
    )

    latched = pnl_by_business_resource_scope.pnl_by_business_resource_failure_for_run(
        tmp_path,
        run_id="bounded-run",
        job_name="pnl_by_business_precompute",
    )

    assert latched is not None
    assert latched["failure_category"] == "resource_over_budget"


def test_bounded_resource_profile_receipts_actual_task_connection_settings(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "receipt.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.close()
    observed: list[tuple[str, int]] = []

    def fake_precompute(**kwargs):
        resource_budget = kwargs["resource_budget"]
        read_conn = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            observed.append(
                (
                    "read_only",
                    int(read_conn.execute("select current_setting('threads')").fetchone()[0]),
                )
            )
        finally:
            read_conn.close()
        resource_budget.enter_write_phase()
        write_conn = duckdb.connect(str(duckdb_path), read_only=False)
        try:
            observed.append(
                (
                    "read_write",
                    int(write_conn.execute("select current_setting('threads')").fetchone()[0]),
                )
            )
        finally:
            write_conn.close()
        return {"year": 2026}

    monkeypatch.setenv(
        pnl_by_business_precompute.PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV,
        pnl_by_business_precompute.PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE,
    )
    monkeypatch.setattr(pnl_by_business_precompute.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(
        pnl_by_business_precompute,
        "_physical_memory_bytes",
        lambda: 32 * 1024**3,
    )
    monkeypatch.setattr(
        pnl_by_business_precompute,
        "_precompute_pnl_by_business_payloads",
        fake_precompute,
    )

    result = pnl_by_business_precompute.precompute_pnl_by_business_payloads(
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
        year=2026,
        as_of_date="2026-08-31",
    )

    assert observed == [("read_only", 8), ("read_write", 8)]
    assert result["resource_limits"]["thread_budget"] == 8
    assert len(result["resource_limits"]["observations"]) == 4
    assert result["resource_limits"]["process_memory_sample_count"] >= 2
    assert result["resource_limits"]["peak_process_memory_sample"]["process_count"] >= 1


def test_small_bounded_resource_budget_fails_before_any_candidate_can_publish(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "small-budget.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.close()
    pointer = tmp_path / "current.json"
    pointer.write_text('{"generation":"sealed-before"}\n', encoding="utf-8")

    def exhaust_small_budget(**_kwargs):
        task_conn = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            task_conn.execute("select list(i) from range(2000000) values(i)").fetchone()
        finally:
            task_conn.close()

    monkeypatch.setenv(
        pnl_by_business_precompute.PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV,
        pnl_by_business_precompute.PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE,
    )
    monkeypatch.setattr(pnl_by_business_precompute.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(
        pnl_by_business_precompute,
        "_physical_memory_bytes",
        lambda: 16 * 1024**2,
    )
    monkeypatch.setattr(
        pnl_by_business_precompute,
        "_precompute_pnl_by_business_payloads",
        exhaust_small_budget,
    )

    with pytest.raises(
        pnl_by_business_precompute.PnlByBusinessResourceBudgetExceeded
    ) as exc_info:
        pnl_by_business_precompute.precompute_pnl_by_business_payloads(
            duckdb_path=str(duckdb_path),
            governance_dir=str(tmp_path / "governance"),
            year=2026,
            as_of_date="2026-08-31",
        )

    assert exc_info.value.receipt["exceeded_process_memory_sample"] is not None
    assert pointer.read_text(encoding="utf-8") == '{"generation":"sealed-before"}\n'
