from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.helpers import load_module


def _load(name: str):
    return load_module(
        f"backend.app.tasks.stock_limit_price_daily_refresh_{name}",
        "backend/app/tasks/stock_limit_price_daily_refresh.py",
    )


def _single_receipt(receipt_dir: Path) -> tuple[Path, dict[str, object]]:
    receipts = list(receipt_dir.glob("*.json"))
    assert len(receipts) == 1
    assert list(receipt_dir.glob("*.tmp")) == []
    return receipts[0], json.loads(receipts[0].read_text(encoding="utf-8"))


def test_cli_defaults_to_dry_run_and_writes_atomic_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load("default_dry_run")
    db_path = tmp_path / "moss.duckdb"
    receipt_dir = tmp_path / "receipts"
    settings = SimpleNamespace(duckdb_path=db_path, tushare_token="")
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(module, "get_settings", lambda: settings)

    def fake_refresh(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "dry_run",
            "trade_date": "2026-08-24",
            "required_code_count": 5211,
        }

    monkeypatch.setattr(
        module, "refresh_stock_limit_prices_for_trade_date", fake_refresh
    )

    exit_code = module.main(
        [
            "--as-of-date",
            "2026-08-24",
            "--receipt-dir",
            str(receipt_dir),
            "--run-id",
            "daily-dry-run",
        ]
    )

    assert exit_code == 0
    assert calls == [
        {
            "duckdb_path": str(db_path),
            "trade_date": "2026-08-24",
            "dry_run": True,
            "run_id": "daily-dry-run",
        }
    ]
    _, receipt = _single_receipt(receipt_dir)
    assert receipt["schema_version"] == module.RECEIPT_SCHEMA_VERSION
    assert receipt["invocation_mode"] == "dry_run"
    assert receipt["status"] == "dry_run"
    assert receipt["exit_code"] == 0


def test_cli_run_once_uses_resolved_source_ip_and_forwards_write_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load("source_ip")
    receipt_dir = tmp_path / "receipts"
    settings = SimpleNamespace(duckdb_path=tmp_path / "moss.duckdb", tushare_token="")
    network_state = {"active": False}
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "resolve_vendor_source_ip", lambda raw: "192.0.2.10")

    @contextmanager
    def fake_network(source_ip: str):
        assert source_ip == "192.0.2.10"
        network_state["active"] = True
        try:
            yield
        finally:
            network_state["active"] = False

    def fake_refresh(**kwargs: object) -> dict[str, object]:
        assert network_state["active"] is True
        calls.append(dict(kwargs))
        return {"status": "completed", "inserted_row_count": 2}

    monkeypatch.setattr(module, "_vendor_source_network", fake_network)
    monkeypatch.setattr(
        module, "refresh_stock_limit_prices_for_trade_date", fake_refresh
    )

    exit_code = module.main(
        [
            "--run-once",
            "--as-of-date",
            "2026-08-24",
            "--source-ip",
            "auto",
            "--receipt-dir",
            str(receipt_dir),
            "--run-id",
            "scheduled-20260824",
        ]
    )

    assert exit_code == 0
    assert calls == [
        {
            "duckdb_path": str(settings.duckdb_path),
            "trade_date": "2026-08-24",
            "dry_run": False,
            "run_id": "scheduled-20260824",
        }
    ]
    _, receipt = _single_receipt(receipt_dir)
    assert receipt["source_ip"] == "192.0.2.10"
    assert receipt["status"] == "completed"


def test_cli_failure_receipt_and_output_redact_configured_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load("redaction")
    receipt_dir = tmp_path / "receipts"
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        tushare_token="SECRET-TOKEN",
    )
    monkeypatch.setenv("MOSS_TUSHARE_TOKEN", "SECRET-TOKEN")
    monkeypatch.setattr(module, "get_settings", lambda: settings)

    def boom(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("upstream SECRET-TOKEN failed api_key=LEAK")

    monkeypatch.setattr(module, "refresh_stock_limit_prices_for_trade_date", boom)

    exit_code = module.main(
        [
            "--run-once",
            "--as-of-date",
            "2026-08-24",
            "--receipt-dir",
            str(receipt_dir),
            "--run-id",
            "failed-run",
        ]
    )

    assert exit_code == 1
    _, receipt = _single_receipt(receipt_dir)
    rendered = json.dumps(receipt, ensure_ascii=False)
    captured = capsys.readouterr()
    assert "SECRET-TOKEN" not in rendered
    assert "SECRET-TOKEN" not in captured.out
    assert "LEAK" not in rendered
    assert "LEAK" not in captured.out
    assert "***" in rendered


@pytest.mark.parametrize("bad_date", ["2026-08-24junk", "2026-8-24", "20260824"])
def test_cli_rejects_non_exact_as_of_date(bad_date: str) -> None:
    module = _load("invalid_date_" + bad_date.replace("-", "_"))
    with pytest.raises(SystemExit) as exc_info:
        module.main(["--as-of-date", bad_date])
    assert exc_info.value.code == 2


def test_cli_rejects_source_ip_without_run_once() -> None:
    module = _load("source_ip_without_write")
    with pytest.raises(SystemExit) as exc_info:
        module.main(["--source-ip", "auto"])
    assert exc_info.value.code == 2
