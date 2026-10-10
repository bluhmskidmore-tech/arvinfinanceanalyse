"""P2 可观测性回归：executive / dashboard 静默降级点必须留日志，且降级行为不变。

覆盖代表性点位：

1. `_fetch_aum_context` 批量取数抛 `RuntimeError`（数据暂缺）→ 逐日回退 + `debug`；
2. `_fetch_aum_context` 批量取数抛 `KeyError`（程序缺陷）→ 同样回退，但升到 `warning`；
3. `_fetch_aum_context` 单日取数异常 → 丢弃该日，日志带 `report_date`；
4. `_fetch_ytd_history` 批量取数异常 → 逐日回退，序列不变；
5. `dashboard_service._fetch_bond_metrics_for_dates` 批量取数异常 → 逐日回退。

每个降级用例都同时断言两件事：
- 降级返回值与「仓库根本没有批量方法」的基线完全一致（行为不变）；
- 日志包含语义、关键上下文（report_date / 日期切片）、异常类型与异常消息。
"""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest

from backend.app.services import dashboard_service as ds
from backend.app.services import executive_service as es

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_executive,
]

_ES_LOGGER = "backend.app.services.executive_service"
_DS_LOGGER = "backend.app.services.dashboard_service"

_AUM_DATES = ["2026-04-08", "2026-04-07", "2026-04-03"]
_AUM_AMOUNTS = {"2026-04-08": 300.0, "2026-04-07": 200.0, "2026-04-03": 100.0}

_YTD_DATES = ["2026-04-08", "2026-03-31", "2026-02-28"]
_YTD_AMOUNTS = {"2026-04-08": 30.0, "2026-03-31": 20.0, "2026-02-28": 10.0}

_DASHBOARD_DATES = ["2026-04-08", "2026-04-07"]


def _degradation_records(caplog: pytest.LogCaptureFixture, marker: str) -> list[logging.LogRecord]:
    return [record for record in caplog.records if marker in record.getMessage()]


class _PerDateAumRepo:
    """只有逐日 formal overview 能力的 balance repo 替身。"""

    def __init__(self) -> None:
        self.per_date_calls: list[str] = []

    def fetch_formal_overview(
        self,
        *,
        report_date: str,
        position_scope: str,
        currency_basis: str,
    ) -> dict[str, object]:
        assert position_scope == "asset"
        assert currency_basis == "CNY"
        self.per_date_calls.append(report_date)
        return {"total_market_value_amount": _AUM_AMOUNTS[report_date]}


class _BrokenBatchAumRepo(_PerDateAumRepo):
    """批量路径必然失败，逐日路径健康 —— 触发批量→逐日的静默降级。"""

    def __init__(self, error: Exception) -> None:
        super().__init__()
        self._error = error

    def fetch_formal_overview_history(self, **_kwargs: object) -> dict[str, object]:
        raise self._error


class _ZqtzOnlyAumRepo:
    """没有 formal overview 能力：`_fetch_executive_aum_row` 直接落到 zqtz 读取。"""

    def __init__(self, *, failing_dates: tuple[str, ...] = ()) -> None:
        self._failing_dates = set(failing_dates)

    def fetch_zqtz_asset_market_value(
        self,
        *,
        report_date: str,
        currency_basis: str = "CNY",
    ) -> dict[str, object]:
        if report_date in self._failing_dates:
            raise RuntimeError(f"zqtz asset market value read failed for {report_date}")
        return {"total_market_value_amount": _AUM_AMOUNTS[report_date]}


class _PerDateYtdRepo:
    def sum_formal_total_pnl_through_report_date(self, report_date: str) -> float:
        return _YTD_AMOUNTS[report_date]


class _BrokenBatchYtdRepo(_PerDateYtdRepo):
    def __init__(self, error: Exception) -> None:
        self._error = error

    def sum_formal_total_pnl_through_report_dates(self, _report_dates: list[str]) -> dict[str, float]:
        raise self._error


class _PerDateDashboardRepo:
    def fetch_bond_core_metrics(self, report_date: str) -> tuple[Decimal, Decimal | None, list[object], bool]:
        return Decimal("1") if report_date == _DASHBOARD_DATES[0] else Decimal("2"), None, [], False


class _BrokenBatchDashboardRepo(_PerDateDashboardRepo):
    def __init__(self, error: Exception) -> None:
        self._error = error

    def fetch_bond_core_metrics_for_dates(self, _report_dates: list[str]) -> dict[str, object]:
        raise self._error


def _aum_context(repo: object) -> tuple[dict[str, dict[str, object]], list[float] | None]:
    return es._fetch_aum_context(
        repo,
        report_dates=_AUM_DATES,
        current_report_date=_AUM_DATES[0],
        n=3,
    )


class TestAumContextBatchDegradation:
    def test_data_gap_logs_debug_and_keeps_per_date_fallback(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        baseline = _aum_context(_PerDateAumRepo())

        degraded_repo = _BrokenBatchAumRepo(RuntimeError("formal overview history unavailable"))
        with caplog.at_level(logging.DEBUG, logger=_ES_LOGGER):
            degraded = _aum_context(degraded_repo)

        # 行为不变：与「没有批量方法」的基线逐字节一致。
        assert degraded == baseline
        assert degraded[1] == [100.0, 200.0, 300.0]
        assert degraded_repo.per_date_calls == _AUM_DATES

        records = _degradation_records(caplog, "aum context batch fetch")
        assert len(records) == 1
        assert records[0].levelno == logging.DEBUG
        message = records[0].getMessage()
        assert "falls back to per-date fetch" in message
        assert "2026-04-08" in message
        assert "RuntimeError" in message
        assert "formal overview history unavailable" in message

    def test_program_defect_logs_warning_without_changing_result(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        baseline = _aum_context(_PerDateAumRepo())

        degraded_repo = _BrokenBatchAumRepo(KeyError("total_market_value_amount"))
        with caplog.at_level(logging.DEBUG, logger=_ES_LOGGER):
            degraded = _aum_context(degraded_repo)

        assert degraded == baseline

        records = _degradation_records(caplog, "aum context batch fetch")
        assert len(records) == 1
        # TypeError / KeyError / AttributeError 属于程序缺陷，必须与数据暂缺区分开。
        assert records[0].levelno == logging.WARNING
        message = records[0].getMessage()
        assert "KeyError" in message
        assert "total_market_value_amount" in message

    def test_healthy_batch_path_emits_no_degradation_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        class _HealthyBatchRepo(_PerDateAumRepo):
            def fetch_formal_overview_history(
                self,
                *,
                report_dates: list[str],
                position_scope: str,
                currency_basis: str,
            ) -> dict[str, dict[str, object]]:
                assert position_scope == "asset"
                assert currency_basis == "CNY"
                return {d: {"total_market_value_amount": _AUM_AMOUNTS[d]} for d in report_dates}

        with caplog.at_level(logging.DEBUG, logger=_ES_LOGGER):
            rows_by_date, values = _aum_context(_HealthyBatchRepo())

        assert values == [100.0, 200.0, 300.0]
        assert set(rows_by_date) == set(_AUM_DATES)
        assert _degradation_records(caplog, "degraded:") == []


class TestAumContextPerDateDegradation:
    def test_failing_date_is_dropped_and_logged_with_report_date(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        healthy_rows, healthy_values = _aum_context(_ZqtzOnlyAumRepo())
        assert healthy_values == [100.0, 200.0, 300.0]

        with caplog.at_level(logging.DEBUG, logger=_ES_LOGGER):
            rows_by_date, values = _aum_context(
                _ZqtzOnlyAumRepo(failing_dates=("2026-04-07",))
            )

        # 行为不变：坏日期照旧被丢弃，其余日期与健康基线一致。
        assert values == [100.0, 300.0]
        assert "2026-04-07" not in rows_by_date
        assert rows_by_date == {d: healthy_rows[d] for d in _AUM_DATES if d != "2026-04-07"}

        records = _degradation_records(caplog, "aum context drops one date")
        assert len(records) == 1
        assert records[0].levelno == logging.DEBUG
        message = records[0].getMessage()
        assert "report_date='2026-04-07'" in message
        assert "RuntimeError" in message
        assert "zqtz asset market value read failed for 2026-04-07" in message


class TestYtdHistoryBatchDegradation:
    def test_batch_failure_falls_back_to_per_date_with_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        baseline = es._fetch_ytd_history(
            _PerDateYtdRepo(),
            report_dates=_YTD_DATES,
            current_report_date=_YTD_DATES[0],
            n=3,
        )

        with caplog.at_level(logging.DEBUG, logger=_ES_LOGGER):
            degraded = es._fetch_ytd_history(
                _BrokenBatchYtdRepo(RuntimeError("formal pnl batch rollup unavailable")),
                report_dates=_YTD_DATES,
                current_report_date=_YTD_DATES[0],
                n=3,
            )

        assert degraded == baseline == [10.0, 20.0, 30.0]

        records = _degradation_records(caplog, "ytd pnl trend batch slice")
        assert len(records) == 1
        assert records[0].levelno == logging.DEBUG
        message = records[0].getMessage()
        assert "2026-04-08" in message
        assert "RuntimeError" in message
        assert "formal pnl batch rollup unavailable" in message


class TestDashboardCoreMetricsBatchDegradation:
    def test_batch_failure_falls_back_to_per_date_with_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        baseline = ds._fetch_bond_metrics_for_dates(_PerDateDashboardRepo(), _DASHBOARD_DATES)

        with caplog.at_level(logging.DEBUG, logger=_DS_LOGGER):
            degraded = ds._fetch_bond_metrics_for_dates(
                _BrokenBatchDashboardRepo(OSError("duckdb file is locked")),
                _DASHBOARD_DATES,
            )

        assert degraded == baseline
        assert degraded["2026-04-08"][0] == Decimal("1")

        records = _degradation_records(caplog, "dashboard bond core metrics batch")
        assert len(records) == 1
        assert records[0].levelno == logging.DEBUG
        message = records[0].getMessage()
        assert "2026-04-08" in message
        assert "OSError" in message
        assert "duckdb file is locked" in message


@pytest.mark.parametrize(
    ("exc", "expected_level"),
    [
        (RuntimeError("gone"), logging.DEBUG),
        (OSError("gone"), logging.DEBUG),
        (ValueError("gone"), logging.DEBUG),
        (TypeError("gone"), logging.WARNING),
        (KeyError("gone"), logging.WARNING),
        (AttributeError("gone"), logging.WARNING),
    ],
)
def test_degradation_level_split(
    caplog: pytest.LogCaptureFixture, exc: Exception, expected_level: int
) -> None:
    with caplog.at_level(logging.DEBUG, logger=_ES_LOGGER):
        es._log_degraded_fallback("probe semantics", exc, report_date="2026-04-08")

    assert [record.levelno for record in caplog.records] == [expected_level]
    assert ds._degraded_log_level(exc) == expected_level
