from __future__ import annotations

import copy
import os
import subprocess
import sys
from calendar import monthrange
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.config import product_category_mapping as mapping
from backend.app.core_finance.product_category_pnl import CanonicalFactRow
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.services.product_category_source_service import SourcePair, _build_source_version
from backend.app.tasks import product_category_pnl as task
from backend.app.tasks import product_category_refresh_state as refresh_state
from backend.app.tasks.product_category_refresh_state import PRODUCT_CATEGORY_TABLES


class RefreshFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.source = root / "source"
        self.source.mkdir()
        self.database = root / "test.duckdb"
        self.governance = root / "governance"
        self.months: list[str] = []
        self.parsed: list[str] = []
        self.calculated: list[tuple[str, str]] = []

    def write(self, month: str, cash: str = "100.123456789") -> None:
        if month not in self.months:
            self.months.append(month)
        (self.source / f"ledger-{month}.xlsx").write_text(cash, encoding="utf-8")
        (self.source / f"average-{month}.xlsx").write_text("365000000.123456789", encoding="utf-8")

    def pairs(self, _source: Path) -> list[SourcePair]:
        result = []
        for month in sorted(self.months):
            ledger = self.source / f"ledger-{month}.xlsx"
            average = self.source / f"average-{month}.xlsx"
            if not ledger.exists() or not average.exists():
                continue
            year, number = int(month[:4]), int(month[4:])
            result.append(SourcePair(
                month_key=month,
                report_date=date(year, number, monthrange(year, number)[1]),
                ledger_path=ledger,
                avg_path=average,
                source_version=_build_source_version(ledger, average),
            ))
        return result

    def facts(self, pair: SourcePair) -> list[CanonicalFactRow]:
        self.parsed.append(pair.month_key)
        cash = Decimal(pair.ledger_path.read_text(encoding="utf-8"))
        scale = Decimal(pair.avg_path.read_text(encoding="utf-8"))
        return [
            CanonicalFactRow(
                report_date=pair.report_date,
                account_code=account,
                currency=currency,
                account_name="Synthetic independent amount",
                beginning_balance=Decimal("0"),
                ending_balance=amount,
                monthly_pnl=cash if account == "50204000001" else Decimal("0"),
                daily_avg_balance=amount,
                annual_avg_balance=amount,
                days_in_period=monthrange(pair.report_date.year, pair.report_date.month)[1],
            )
            for currency in ("CNX", "CNY")
            for account, amount in (("120", scale), ("50204000001", Decimal("0")))
        ]

    def run(self, *, database: Path | None = None, governance: Path | None = None) -> dict[str, object]:
        return task.materialize_product_category_pnl_sync(
            duckdb_path=str(database or self.database),
            source_dir=str(self.source),
            governance_dir=str(governance or self.governance),
        )

    def rows(self, database: Path | None = None) -> dict[str, list[tuple]]:
        with duckdb.connect(str(database or self.database), read_only=True) as connection:
            return {table: connection.execute(f"select * from {table} order by all").fetchall() for table in PRODUCT_CATEGORY_TABLES}

    def clean_reference(self) -> dict[str, list[tuple]]:
        # An independent empty database cannot reuse previous materialization state.
        reference = self.root / "reference.duckdb"
        reference_governance = self.root / "reference-governance"
        if reference.exists():
            reference.unlink()
        repo = GovernanceRepository(base_dir=reference_governance)
        old_events = repo.read_all(task.PRODUCT_CATEGORY_ADJUSTMENT_STREAM)
        assert not old_events, "each test should request one clean reference"
        for event in GovernanceRepository(base_dir=self.governance).read_all(task.PRODUCT_CATEGORY_ADJUSTMENT_STREAM):
            repo.append(task.PRODUCT_CATEGORY_ADJUSTMENT_STREAM, event)
        self.run(database=reference, governance=reference_governance)
        return self.rows(reference)

    def state(self) -> dict[str, object]:
        manifest = GovernanceRepository(base_dir=self.governance).read_latest_manifest("product_category_pnl.formal")
        assert manifest is not None
        return manifest["lineage"]["product_category_refresh"]

    def adjustment(self, *, day: str, status: str = "approved", amount: str = "10", revision: int = 1) -> None:
        GovernanceRepository(base_dir=self.governance).append(task.PRODUCT_CATEGORY_ADJUSTMENT_STREAM, {
            "adjustment_id": "independent-delta",
            "report_date": day,
            "created_at": f"2026-03-{revision:02d}T00:00:00Z",
            "operator": "DELTA",
            "approval_status": status,
            "account_code": "50204000001",
            "currency": "CNX",
            "monthly_pnl": amount,
        })


@pytest.fixture
def refresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Other suites reload or evict task modules after collection. The code
    # fingerprint must inspect the same modules this fixture executes and patches.
    for module in (task, refresh_state):
        monkeypatch.setitem(sys.modules, module.__name__, module)
        parent_name, _, child_name = module.__name__.rpartition(".")
        monkeypatch.setitem(vars(sys.modules[parent_name]), child_name, module)
    fixture = RefreshFixture(tmp_path)
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(fixture.database))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(fixture.governance))
    get_settings.cache_clear()
    for month in ("202501", "202601", "202602"):
        fixture.write(month)
    monkeypatch.setattr(task, "discover_source_pairs", fixture.pairs)
    monkeypatch.setattr(task, "build_canonical_facts", fixture.facts)
    original = task.calculate_read_model

    def calculate(facts, report_date, view, config):
        fixture.calculated.append((report_date.isoformat(), view))
        return original(facts, report_date, view, config)

    monkeypatch.setattr(task, "calculate_read_model", calculate)
    yield fixture
    get_settings.cache_clear()


def test_unchanged_input_skips_parsing_calculation_and_preserves_all_values(refresh: RefreshFixture) -> None:
    initial = refresh.run()
    before = refresh.rows()
    refresh.parsed.clear()
    refresh.calculated.clear()

    repeated = refresh.run()

    assert refresh.parsed == []
    assert refresh.calculated == []
    assert repeated["month_count"] == initial["month_count"] == 3
    assert repeated["report_dates"] == initial["report_dates"]
    scope = repeated["refresh_scope"]
    assert scope["scanned_report_dates"] == initial["report_dates"]
    assert scope["scanned_years"] == ["2025", "2026"]
    assert scope["scanned_date_count"] == 3
    assert scope["rebuilt_report_dates"] == []
    assert scope["rebuilt_years"] == []
    assert scope["rebuilt_date_count"] == 0
    assert scope["reused_report_dates"] == initial["report_dates"]
    assert scope["reused_years"] == ["2025", "2026"]
    assert scope["reused_date_count"] == 3
    assert scope["removed_report_dates"] == []
    assert scope["removed_years"] == []
    assert scope["removed_date_count"] == 0
    assert refresh.rows() == before
    assert refresh.state()["rebuilt_years"] == []
    assert refresh.state()["reused_years"] == ["2025", "2026"]
    runs = GovernanceRepository(base_dir=refresh.governance).read_all(CACHE_BUILD_RUN_STREAM)
    assert runs[-1]["status"] == "completed"


@pytest.mark.parametrize("changed_month", ["202601", "202602"])
def test_revision_rebuilds_only_affected_year_and_equals_clean_full_with_original_precision(
    refresh: RefreshFixture, changed_month: str,
) -> None:
    refresh.run()
    before = refresh.rows()
    refresh.parsed.clear()
    refresh.calculated.clear()
    refresh.write(changed_month, "900.987654321")

    receipt = refresh.run()

    assert refresh.parsed == ["202601", "202602"]
    assert len(refresh.calculated) == 8
    assert refresh.state()["rebuilt_years"] == ["2026"]
    assert receipt["refresh_scope"]["rebuilt_report_dates"] == ["2026-01-31", "2026-02-28"]
    assert receipt["refresh_scope"]["rebuilt_years"] == ["2026"]
    assert receipt["refresh_scope"]["rebuilt_date_count"] == 2
    assert receipt["refresh_scope"]["reused_report_dates"] == ["2025-01-31"]
    assert receipt["refresh_scope"]["reused_years"] == ["2025"]
    after = refresh.rows()
    assert {table: [row for row in rows if row[0].startswith("2025")] for table, rows in after.items()} == {
        table: [row for row in rows if row[0].startswith("2025")] for table, rows in before.items()
    }
    assert after == refresh.clean_reference()
    with duckdb.connect(str(refresh.database), read_only=True) as connection:
        cash = connection.execute("""
            select cnx_cash from product_category_pnl_formal_read_model
            where report_date = '2026-02-28' and view = 'ytd' and category_id = 'asset_total'
        """).fetchone()[0]
    assert cash == Decimal("1001.11111111")


def test_source_content_change_with_same_size_and_mtime_is_not_a_noop(refresh: RefreshFixture) -> None:
    refresh.run()
    path = refresh.source / "ledger-202602.xlsx"
    old_stat = path.stat()
    path.write_text("900.123456789", encoding="utf-8")
    os.utime(path, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
    assert path.stat().st_size == old_stat.st_size
    refresh.parsed.clear()

    refresh.run()

    assert refresh.parsed == ["202601", "202602"]
    assert refresh.rows() == refresh.clean_reference()


@pytest.mark.parametrize("final_status", ["approved", "rejected"])
def test_moved_or_revoked_delta_rebuilds_both_years_without_double_application(
    refresh: RefreshFixture, final_status: str,
) -> None:
    refresh.adjustment(day="2025-01-31")
    refresh.run()
    refresh.adjustment(day="2026-02-28", status=final_status, amount="12", revision=2)
    refresh.parsed.clear()

    refresh.run()

    assert refresh.parsed == ["202501", "202601", "202602"]
    assert refresh.rows() == refresh.clean_reference()
    with duckdb.connect(str(refresh.database), read_only=True) as connection:
        values = connection.execute("""
            select report_date, monthly_pnl from product_category_pnl_canonical_fact
            where account_code = '50204000001' and currency = 'CNX' order by report_date
        """).fetchall()
    assert values[0][1] == Decimal("100.12345679")
    assert values[-1][1] == Decimal("112.12345679" if final_status == "approved" else "100.12345679")


def test_year_configuration_change_rebuilds_only_that_year(
    refresh: RefreshFixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    refresh.run()
    refresh.parsed.clear()
    monkeypatch.setitem(mapping.FTP_RATE_PCT_BY_REPORT_YEAR, 2025, Decimal("2.25"))

    refresh.run()

    assert refresh.parsed == ["202501"]
    assert refresh.rows() == refresh.clean_reference()


@pytest.mark.parametrize("month", ["202501", "202601"])
def test_deleted_month_or_entire_year_is_removed_and_remaining_outputs_equal_full(
    refresh: RefreshFixture, month: str,
) -> None:
    refresh.run()
    (refresh.source / f"average-{month}.xlsx").unlink()

    receipt = refresh.run()

    assert receipt["month_count"] == 2
    scope = receipt["refresh_scope"]
    assert scope["scanned_date_count"] == 2
    assert scope["removed_report_dates"] == ["2025-01-31" if month == "202501" else "2026-01-31"]
    assert scope["removed_date_count"] == 1
    assert scope["removed_years"] == (["2025"] if month == "202501" else [])
    assert scope["rebuilt_report_dates"] == ([] if month == "202501" else ["2026-02-28"])
    assert all(not row[0].replace("-", "").startswith(month) for rows in refresh.rows().values() for row in rows)
    assert refresh.rows() == refresh.clean_reference()


def test_empty_source_set_fails_without_removing_existing_results(refresh: RefreshFixture) -> None:
    refresh.run()
    before = refresh.rows()
    for month in refresh.months:
        (refresh.source / f"average-{month}.xlsx").unlink()

    with pytest.raises(ValueError, match="No product-category source pairs"):
        refresh.run()

    assert refresh.rows() == before


@pytest.mark.parametrize("tamper", ["missing", "same_count", "scenario", "unknown_date"])
def test_stored_integrity_detects_missing_modified_and_unexpected_rows(
    refresh: RefreshFixture, tamper: str,
) -> None:
    refresh.run()
    with duckdb.connect(str(refresh.database)) as connection:
        if tamper == "missing":
            connection.execute("delete from product_category_pnl_formal_read_model where report_date = '2026-02-28' and view = 'ytd'")
        elif tamper == "same_count":
            connection.execute("update product_category_pnl_canonical_fact set monthly_pnl = monthly_pnl + 1 where report_date = '2026-01-31'")
        elif tamper == "scenario":
            connection.execute("insert into product_category_pnl_scenario_read_model (report_date, cnx_cash) values ('2026-02-28', 77)")
        else:
            connection.execute("insert into product_category_pnl_canonical_fact (report_date, monthly_pnl) values (NULL, 77)")
    refresh.parsed.clear()

    refresh.run()

    assert refresh.parsed == ([] if tamper == "unknown_date" else ["202601", "202602"])
    assert refresh.rows() == refresh.clean_reference()


def test_calculation_failure_rolls_back_and_next_attempt_rebuilds_conservatively(
    refresh: RefreshFixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    refresh.run()
    before = refresh.rows()
    refresh.write("202602", "999.123456789")
    original = task.calculate_read_model

    def fail(*_args):
        raise RuntimeError("controlled calculation failure")

    monkeypatch.setattr(task, "calculate_read_model", fail)
    with pytest.raises(RuntimeError, match="controlled calculation failure"):
        refresh.run()
    assert refresh.rows() == before
    monkeypatch.setattr(task, "calculate_read_model", original)
    refresh.parsed.clear()

    refresh.run()

    assert refresh.parsed == ["202501", "202601", "202602"]
    assert refresh.rows() == refresh.clean_reference()


@pytest.mark.parametrize("invalid_metadata", ["legacy", "protocol", "rule", "implementation"])
def test_unknown_or_changed_certification_rebuilds_all_years(
    refresh: RefreshFixture, monkeypatch: pytest.MonkeyPatch, invalid_metadata: str,
) -> None:
    refresh.run()
    repo = GovernanceRepository(base_dir=refresh.governance)
    manifest = copy.deepcopy(repo.read_latest_manifest("product_category_pnl.formal"))
    if invalid_metadata == "legacy":
        manifest.pop("lineage")
    elif invalid_metadata == "protocol":
        manifest["lineage"]["product_category_refresh"]["version"] = -1
    elif invalid_metadata == "rule":
        monkeypatch.setattr(task, "RULE_VERSION", "synthetic-new-rule")
    else:
        monkeypatch.setattr(task, "implementation_signature", lambda: "synthetic-new-implementation")
    repo.append(CACHE_MANIFEST_STREAM, manifest)
    refresh.parsed.clear()

    refresh.run()

    assert refresh.parsed == ["202501", "202601", "202602"]
    assert refresh.rows() == refresh.clean_reference()


def test_failed_manifest_write_never_certifies_reuse(
    refresh: RefreshFixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    refresh.run()
    original = GovernanceRepository.append_many_atomic

    def fail(_repo, _entries):
        raise OSError("controlled receipt failure")

    monkeypatch.setattr(GovernanceRepository, "append_many_atomic", fail)
    with pytest.raises(OSError, match="controlled receipt failure"):
        refresh.run()
    monkeypatch.setattr(GovernanceRepository, "append_many_atomic", original)
    refresh.parsed.clear()

    refresh.run()

    assert refresh.parsed == ["202501", "202601", "202602"]
    assert refresh.rows() == refresh.clean_reference()


def test_inputs_changed_during_parse_abort_without_certifying_mixed_inputs(
    refresh: RefreshFixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    refresh.run()
    before = refresh.rows()
    refresh.write("202602", "900.123456789")
    original = task.build_canonical_facts

    def change_after_parse(pair):
        facts = original(pair)
        if pair.month_key == "202602":
            refresh.write("202602", "800.123456789")
        return facts

    monkeypatch.setattr(task, "build_canonical_facts", change_after_parse)
    with pytest.raises(ValueError, match="inputs changed during materialization"):
        refresh.run()
    assert refresh.rows() == before
    assert GovernanceRepository(base_dir=refresh.governance).read_all(CACHE_BUILD_RUN_STREAM)[-1]["status"] == "failed"


def test_worker_rejects_files_changed_after_import_without_new_manifest(
    refresh: RefreshFixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    refresh.run()
    before = refresh.rows()
    repo = GovernanceRepository(base_dir=refresh.governance)
    manifest = repo.read_latest_manifest("product_category_pnl.formal")
    original = Path.read_bytes

    def changed_file(path: Path) -> bytes:
        content = original(path)
        if path.name == "field_normalization.py":
            return content + b"\n# simulated deployed revision\n"
        return content

    monkeypatch.setattr(Path, "read_bytes", changed_file)
    with pytest.raises(RuntimeError, match="restart the worker"):
        refresh.run()

    assert refresh.rows() == before
    assert repo.read_latest_manifest("product_category_pnl.formal") == manifest
    assert repo.read_all(CACHE_BUILD_RUN_STREAM)[-1]["status"] == "failed"


def test_implementation_signature_is_stable_in_fresh_processes(refresh: RefreshFixture) -> None:
    command = [
        sys.executable, "-c",
        "from backend.app.tasks import product_category_pnl as task; print(task.implementation_signature())",
    ]
    signatures = []
    for seed in ("7", "19"):
        result = subprocess.run(
            command, cwd=Path(refresh_state.__file__).resolve().parents[3],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True, text=True, check=True, timeout=30,
        )
        signatures.append(result.stdout.strip().splitlines()[-1])
    assert len(signatures[0]) == 64
    assert signatures[0] == signatures[1]
