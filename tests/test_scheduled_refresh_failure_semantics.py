from __future__ import annotations

from datetime import date

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError

from backend.app.tasks import (
    choice_macro,
)
from backend.app.tasks import (
    macro_toolkit_freshness_refresh as freshness,
)

_PUBLIC_LOADER_NAMES = (
    "_fetch_public_bond_zh_us_history_rows",
    "_fetch_public_dr007_history_rows",
    "_fetch_tushare_cross_asset_history_rows",
    "_fetch_tushare_commodity_futures_cross_asset_history_rows",
    "_fetch_public_brent_history_rows",
    "_fetch_public_steel_history_rows",
    "_fetch_public_fx_history_rows",
)


def _loader_named(name: str, result: object):
    def loader(**_kwargs):
        if isinstance(result, BaseException):
            raise result
        return result

    loader.__name__ = name
    return loader


def _patch_public_loaders(monkeypatch, results: list[object]) -> None:
    assert len(results) == len(_PUBLIC_LOADER_NAMES)
    for name, result in zip(_PUBLIC_LOADER_NAMES, results, strict=True):
        monkeypatch.setattr(choice_macro, name, _loader_named(name, result))


def _public_row(series_id: str = "CA.CSI300") -> dict[str, object]:
    return {
        "series_id": series_id,
        "trade_date": "2026-07-20",
        "value_numeric": 4102.25,
        "vendor_version": "vv_test",
        "source_version": "sv_test",
    }


def test_public_cross_asset_partial_reports_warning_count_and_failed_sources(
    monkeypatch,
    tmp_path,
) -> None:
    failures = [
        ValueError(f"invalid parameters for {name}") for name in _PUBLIC_LOADER_NAMES[1:]
    ]
    _patch_public_loaders(monkeypatch, [[_public_row()], *failures])

    result = choice_macro.refresh_public_cross_asset_headlines(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        report_date="2026-07-20",
    )

    assert result["status"] == "partial"
    assert result["row_count"] == 1
    assert result["warning_count"] == 6
    assert result["failed_sources"] == list(_PUBLIC_LOADER_NAMES[1:])
    assert result["covered_required_series"] == ["CA.CSI300"]


def test_public_cross_asset_non_retryable_total_failure_returns_failed(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_public_loaders(
        monkeypatch,
        [ValueError(f"invalid parameters for {name}") for name in _PUBLIC_LOADER_NAMES],
    )

    result = choice_macro.refresh_public_cross_asset_headlines(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        report_date="2026-07-20",
    )

    assert result["status"] == "failed"
    assert result["row_count"] == 0
    assert result["series_count"] == 0
    assert result["warning_count"] == 7
    assert result["failed_sources"] == list(_PUBLIC_LOADER_NAMES)


def test_public_cross_asset_network_total_failure_raises_for_dramatiq_retry(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_public_loaders(
        monkeypatch,
        [RequestsConnectionError(f"offline: {name}") for name in _PUBLIC_LOADER_NAMES],
    )

    with pytest.raises(choice_macro.PublicCrossAssetRetryableError, match="7 required sources"):
        choice_macro.refresh_public_cross_asset_headlines(
            duckdb_path=str(tmp_path / "moss.duckdb"),
            report_date="2026-07-20",
        )


def test_cffex_only_falls_back_when_all_source_attempts_are_empty(monkeypatch) -> None:
    calls: list[str] = []

    def materialize(**kwargs):
        trade_date = str(kwargs["trade_date"])
        calls.append(trade_date)
        if len(calls) == 1:
            return {
                "row_count": 0,
                "attempts": [
                    {
                        "status": "empty",
                        "detail": "no rows returned",
                        "source_vendor": "tushare",
                        "contract": "T.CFE",
                    }
                ],
            }
        return {
            "row_count": 2,
            "attempts": [
                {
                    "status": "materialized",
                    "detail": "",
                    "source_vendor": "tushare",
                    "contract": "T.CFE",
                    "row_count": 2,
                }
            ],
        }

    monkeypatch.setattr(freshness, "materialize_cffex_member_rank", materialize)

    result = freshness._run_cffex_step(
        report_date=date(2026, 7, 20),
        duckdb_path="F:/tmp/moss.duckdb",
    )

    assert calls == ["2026-07-20", "2026-07-17"]
    assert result["status"] == "success"
    assert result["result"]["attempts"][0]["status"] == "zero_rows"
    assert result["result"]["attempts"][0]["source_attempts"][0] == {
        "status": "empty",
        "detail": "no rows returned",
        "source_vendor": "tushare",
        "contract": "T.CFE",
    }


def test_cffex_error_attempt_blocks_date_fallback_and_preserves_detail(monkeypatch) -> None:
    calls: list[str] = []

    def materialize(**kwargs):
        calls.append(str(kwargs["trade_date"]))
        return {
            "row_count": 0,
            "attempts": [
                {
                    "status": "empty",
                    "detail": "no rows returned",
                    "source_vendor": "tushare",
                    "contract": "T.CFE",
                },
                {
                    "status": "error",
                    "error_type": "ValueError",
                    "detail": "invalid exchange parameter",
                    "source_vendor": "tushare",
                    "contract": "TF.CFE",
                },
            ],
        }

    monkeypatch.setattr(freshness, "materialize_cffex_member_rank", materialize)

    result = freshness._run_cffex_step(
        report_date=date(2026, 7, 20),
        duckdb_path="F:/tmp/moss.duckdb",
    )

    assert calls == ["2026-07-20"]
    assert result["status"] == "failed"
    assert result["result"]["attempts"][0]["source_attempts"][1]["error_type"] == "ValueError"
    assert "ValueError" in str(result["reason"])
    assert "invalid exchange parameter" in str(result["reason"])


def test_cffex_network_attempt_raises_for_dramatiq_retry(monkeypatch) -> None:
    monkeypatch.setattr(
        freshness,
        "materialize_cffex_member_rank",
        lambda **_kwargs: {
            "row_count": 0,
            "attempts": [
                {
                    "status": "error",
                    "error_type": "ConnectionError",
                    "detail": "vendor connection reset",
                    "source_vendor": "tushare",
                    "contract": "T.CFE",
                }
            ],
        },
    )

    with pytest.raises(freshness.RetryableFreshnessError, match="ConnectionError"):
        freshness._run_cffex_step(
            report_date=date(2026, 7, 20),
            duckdb_path="F:/tmp/moss.duckdb",
        )


def test_cffex_authentication_attempt_returns_failed_without_retry(monkeypatch) -> None:
    monkeypatch.setattr(
        freshness,
        "materialize_cffex_member_rank",
        lambda **_kwargs: {
            "row_count": 0,
            "attempts": [
                {
                    "status": "error",
                    "error_type": "AuthenticationError",
                    "detail": "invalid token",
                    "source_vendor": "tushare",
                    "contract": "T.CFE",
                }
            ],
        },
    )

    result = freshness._run_cffex_step(
        report_date=date(2026, 7, 20),
        duckdb_path="F:/tmp/moss.duckdb",
    )

    assert result["status"] == "failed"
    assert "AuthenticationError" in str(result["reason"])
    assert "invalid token" in str(result["reason"])


def test_required_partial_result_degrades_instead_of_failing() -> None:
    receipt = freshness._run_required_step(
        step="public_cross_asset_headlines",
        fn=lambda: {
            "status": "partial",
            "row_count": 3,
            "warning_count": 1,
            "failed_sources": ["_fetch_public_brent_history_rows"],
        },
        result_fields=("status", "row_count", "warning_count", "failed_sources"),
    )

    assert receipt["status"] == "degraded"
    assert receipt["result"]["warning_count"] == 1
    assert receipt["result"]["failed_sources"] == ["_fetch_public_brent_history_rows"]


def test_required_network_exception_is_not_folded_into_failed_result() -> None:
    def fail() -> object:
        raise ConnectionError("upstream reset")

    with pytest.raises(ConnectionError, match="upstream reset"):
        freshness._run_required_step(
            step="public_cross_asset_headlines",
            fn=fail,
            result_fields=("status", "row_count"),
        )
