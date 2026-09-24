"""choice_stock 摄入 vendor 标签守卫测试。

覆盖(契约 docs/data_contracts.md §4.10):
1. daily observation 行的 vendor_version 按 daily_ohlcv_amount 实际来源打标,
   不受其他 field_key 请求 fallback 影响;混源 fail-loud;
2. 历史重放代际守卫:native 标签不得写 tushare 封存区(<=2025-12-31),
   tushare 标签不得写 choice_native 区(>=2026-01-05),默认 fail-loud,
   allow_cross_era_backfill=True 受控放行;
3. 写入后 DQ 观察模式检查:vendor 白名单、(stock_code, trade_date) 重复、
   amount/(volume*close) 抽样恒等式;
4. run 级/daily 级 vendor 分叉时(OHLCV native + 其他请求 fallback),
   manifest 落地验证与 committed-lineage 解析按 daily 行实际 vendor 工作;
5. 盘后补充脚本(supplement_livermore_after_close_inputs)写入路径接入
   vendor 白名单 + 代际守卫。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pandas as pd
import pytest

from backend.app.tasks.choice_stock_materialize import (
    ChoiceStockOhlcvMixedSourceError,
    ChoiceStockUnknownVendorVersionError,
    ChoiceStockVendorEraViolationError,
    _resolve_daily_observation_vendor_prefix,
    assert_known_choice_stock_daily_vendor_version,
    ensure_choice_stock_schema,
    materialize_choice_stock_inputs,
    run_choice_stock_daily_observation_dq_checks,
)
from backend.app.tasks.choice_stock_observation_manifest import (
    build_choice_stock_observation_manifest,
    resolve_latest_committed_choice_stock_observation,
    verify_choice_stock_daily_observation_landing,
)
from tests.helpers import load_module
from tests.test_choice_stock_materialize import (
    FakeChoiceStockClient,
    FakeTushareStockClient,
    PermissionDeniedCsdChoiceStockClient,
    _write_confirmed_catalog,
)


class SectorStrengthDeniedChoiceStockClient(FakeChoiceStockClient):
    """仅 sector_strength(PCTCHANGE 等)csd 请求权限被拒;OHLCV/status/limit 走 Choice native。"""

    def csd(self, *args: object, options: str = "") -> Any:
        indicators = str(args[1])
        if "PCTCHANGE" in indicators:
            self.calls.append(("csd", args, options))
            return SimpleNamespace(ErrorCode=10001012, ErrorMsg="insufficient user access for sector strength")
        return super().csd(*args, options=options)


class Era2025ChoiceStockClient(FakeChoiceStockClient):
    """Choice native csd 返回落在 tushare 封存区内的交易日行(模拟历史重放请求)。"""

    def csd(self, *args: object, options: str = "") -> Any:
        result = super().csd(*args, options=options)
        result.Dates = ["2025-06-16"]
        return result


class Era2025TushareStockClient(FakeTushareStockClient):
    """把 Tushare fallback 行全部落在 tushare 代际封存区内(2025-06-15)。"""

    _TRADE_DATE = "20250615"

    def trade_cal(self, **kwargs: object) -> pd.DataFrame:
        self.calls.append(("trade_cal", kwargs))
        return pd.DataFrame([{"cal_date": self._TRADE_DATE, "is_open": 1}])

    def daily(self, **kwargs: object) -> pd.DataFrame:
        frame = super().daily(**kwargs)
        frame["trade_date"] = self._TRADE_DATE
        return frame

    def daily_basic(self, **kwargs: object) -> pd.DataFrame:
        frame = super().daily_basic(**kwargs)
        frame["trade_date"] = self._TRADE_DATE
        return frame

    def stk_limit(self, **kwargs: object) -> pd.DataFrame:
        frame = super().stk_limit(**kwargs)
        frame["trade_date"] = self._TRADE_DATE
        return frame


def test_daily_vendor_stays_native_when_only_non_ohlcv_request_falls_back(tmp_path: Path) -> None:
    """①OHLCV native 成功、其他请求 fallback 时,daily 行标签仍为 native。"""

    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)

    result = materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=SectorStrengthDeniedChoiceStockClient(),
        tushare_client=FakeTushareStockClient(),
    )

    assert result["status"] == "completed"
    # run 级标签仍记录"本次 run 发生过 Tushare fallback"(审计语义不变)
    assert str(result["vendor_version"]).startswith("vv_choice_tushare_stock_20260428_")
    # daily observation 行按 OHLCV 实际来源(Choice native)打标,不含 tushare 子串
    assert str(result["daily_vendor_version"]).startswith("vv_choice_stock_20260428_")

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        vendors = conn.execute("select distinct vendor_version from choice_stock_daily_observation").fetchall()
        audits = conn.execute(
            "select field_key, status from choice_stock_request_audit where call = 'csd' order by field_key"
        ).fetchall()
    finally:
        conn.close()
    assert vendors == [(result["daily_vendor_version"],)]
    assert ("daily_return_turnover_amplitude", "completed_tushare_fallback") in audits
    assert ("daily_ohlcv_amount", "completed") in audits
    # FakeChoiceStockClient 的 OHLCV 数值满足 native 恒等式(10500/(1000*10.5)=1.0)
    assert result["dq_checks"]["status"] == "passed"


def test_daily_vendor_is_tushare_when_ohlcv_falls_back_within_tushare_era(tmp_path: Path) -> None:
    """②OHLCV 走 Tushare fallback 时标签为 tushare(2025 封存区日期,无需 override)。"""

    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)

    result = materialize_choice_stock_inputs(
        as_of_date="2025-06-15",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=PermissionDeniedCsdChoiceStockClient(),
        tushare_client=Era2025TushareStockClient(),
    )

    assert result["status"] == "completed"
    assert str(result["daily_vendor_version"]).startswith("vv_choice_tushare_stock_20250615_")

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            "select distinct trade_date, vendor_version from choice_stock_daily_observation"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [("2025-06-15", result["daily_vendor_version"])]
    # fake 数据 amount/(volume*close)=1.0,偏离 tushare 代际预期 0.1 -> 恒等式观察告警
    assert result["dq_checks"]["status"] == "warning"
    assert any("suspected unit mislabeling" in issue for issue in result["dq_checks"]["issues"])


def test_tushare_fallback_rows_in_native_era_rejected_by_default(tmp_path: Path) -> None:
    """tushare 标签写 >=2026-01-05 的行默认 fail-loud,拒绝整个写入。"""

    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)

    with pytest.raises(ChoiceStockVendorEraViolationError, match=r"4\.10"):
        materialize_choice_stock_inputs(
            as_of_date="2026-04-28",
            duckdb_path=str(duckdb_path),
            catalog_path=str(catalog_path),
            client=PermissionDeniedCsdChoiceStockClient(),
            tushare_client=FakeTushareStockClient(),
        )
    # 写入发生前即被拒绝:库文件都不应存在
    assert not duckdb_path.exists()


def test_native_rows_in_tushare_era_rejected_then_allowed_by_override(tmp_path: Path) -> None:
    """③native 标签写 <=2025-12-31 的行默认被拒;allow_cross_era_backfill=True 受控放行。"""

    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)

    with pytest.raises(ChoiceStockVendorEraViolationError, match=r"sealed tushare era"):
        materialize_choice_stock_inputs(
            as_of_date="2025-06-16",
            duckdb_path=str(duckdb_path),
            catalog_path=str(catalog_path),
            client=Era2025ChoiceStockClient(),
            tushare_client=FakeTushareStockClient(),
        )
    assert not duckdb_path.exists()

    result = materialize_choice_stock_inputs(
        as_of_date="2025-06-16",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=Era2025ChoiceStockClient(),
        tushare_client=FakeTushareStockClient(),
        allow_cross_era_backfill=True,
    )

    assert result["status"] == "completed"
    assert str(result["daily_vendor_version"]).startswith("vv_choice_stock_20250616_")
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            "select distinct trade_date, vendor_version from choice_stock_daily_observation"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [("2025-06-16", result["daily_vendor_version"])]


def test_mixed_ohlcv_sources_fail_loud() -> None:
    """同一 run 内 OHLCV 混源(理论防御分支)必须拒绝单标签写入。"""

    with pytest.raises(ChoiceStockOhlcvMixedSourceError, match="mixes sources"):
        _resolve_daily_observation_vendor_prefix(
            ohlcv_source_tags={"choice", "tushare"},
            daily_row_count=10,
            as_of_date="2026-04-28",
        )
    with pytest.raises(ChoiceStockOhlcvMixedSourceError, match="no daily_ohlcv_amount source"):
        _resolve_daily_observation_vendor_prefix(
            ohlcv_source_tags=set(),
            daily_row_count=10,
            as_of_date="2026-04-28",
        )


_VALID_NATIVE_VENDOR = "vv_choice_stock_20260428_0123456789ab"


def _dq_conn(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(str(tmp_path / "dq.duckdb"))
    ensure_choice_stock_schema(conn)
    return conn


def _insert_daily_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    trade_date: str,
    stock_code: str,
    run_id: str,
    vendor_version: str,
    amount: float,
    volume: float,
    close_value: float,
) -> None:
    conn.execute(
        "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            trade_date,
            stock_code,
            close_value,
            close_value,
            close_value,
            close_value,
            volume,
            amount,
            None,
            None,
            None,
            "Trading",
            "",
            "",
            "[]",
            "sv_choice_stock_test",
            vendor_version,
            "rv_test",
            run_id,
        ],
    )


def test_dq_checks_flag_blank_and_unknown_vendor_version(tmp_path: Path) -> None:
    """④a vendor_version 空白或不在已知代际模式白名单内 -> 告警。"""

    conn = _dq_conn(tmp_path)
    try:
        _insert_daily_row(
            conn, trade_date="2026-04-28", stock_code="000001.SZ", run_id="r1",
            vendor_version="  ", amount=10500.0, volume=1000.0, close_value=10.5,
        )
        _insert_daily_row(
            conn, trade_date="2026-04-28", stock_code="600000.SH", run_id="r1",
            vendor_version="vv_mystery_vendor_x", amount=10500.0, volume=1000.0, close_value=10.5,
        )
        report = run_choice_stock_daily_observation_dq_checks(
            conn, run_id="r1", expected_vendor_version=_VALID_NATIVE_VENDOR
        )
    finally:
        conn.close()
    assert report["status"] == "warning"
    assert any("whitelist" in issue for issue in report["issues"])
    assert set(report["checks"]["vendor_version_whitelist"]["unknown_or_blank"]) == {"  ", "vv_mystery_vendor_x"}


def test_dq_checks_flag_duplicate_keys(tmp_path: Path) -> None:
    """④b 本次写入范围内 (stock_code, trade_date) 重复 -> 告警。"""

    conn = _dq_conn(tmp_path)
    try:
        for _ in range(2):
            _insert_daily_row(
                conn, trade_date="2026-04-28", stock_code="000001.SZ", run_id="r1",
                vendor_version=_VALID_NATIVE_VENDOR, amount=10500.0, volume=1000.0, close_value=10.5,
            )
        report = run_choice_stock_daily_observation_dq_checks(
            conn, run_id="r1", expected_vendor_version=_VALID_NATIVE_VENDOR
        )
    finally:
        conn.close()
    assert report["status"] == "warning"
    assert any("duplicated (stock_code, trade_date)" in issue for issue in report["issues"])
    assert report["checks"]["duplicate_keys"]["duplicate_key_count"] == 1


def test_dq_checks_flag_identity_ratio_mislabel(tmp_path: Path) -> None:
    """④c native 标签但抽样恒等式中位比值≈0.1(像 tushare 单位) -> 疑似单位错标告警。"""

    conn = _dq_conn(tmp_path)
    try:
        _insert_daily_row(
            conn, trade_date="2026-04-28", stock_code="000001.SZ", run_id="r1",
            vendor_version=_VALID_NATIVE_VENDOR, amount=1050.0, volume=1000.0, close_value=10.5,
        )
        report = run_choice_stock_daily_observation_dq_checks(
            conn, run_id="r1", expected_vendor_version=_VALID_NATIVE_VENDOR
        )
    finally:
        conn.close()
    assert report["status"] == "warning"
    assert any("suspected unit mislabeling" in issue for issue in report["issues"])
    assert report["checks"]["amount_volume_close_identity"]["median_ratio"] == pytest.approx(0.1)


def test_dq_checks_pass_for_clean_native_batch(tmp_path: Path) -> None:
    """干净 native 批次(白名单命中/无重复/比值≈1.0)-> passed。"""

    conn = _dq_conn(tmp_path)
    try:
        _insert_daily_row(
            conn, trade_date="2026-04-28", stock_code="000001.SZ", run_id="r1",
            vendor_version=_VALID_NATIVE_VENDOR, amount=10500.0, volume=1000.0, close_value=10.5,
        )
        report = run_choice_stock_daily_observation_dq_checks(
            conn, run_id="r1", expected_vendor_version=_VALID_NATIVE_VENDOR
        )
    finally:
        conn.close()
    assert report["status"] == "passed"
    assert report["issues"] == []


def test_manifest_verification_uses_daily_vendor_when_run_vendor_diverges(tmp_path: Path) -> None:
    """⑤OHLCV native + 其他请求 fallback(run 标 tushare、daily 行标 native)时,
    落地验证与 committed-lineage 解析必须按 daily 行实际 vendor 通过。"""

    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)

    result = materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=SectorStrengthDeniedChoiceStockClient(),
        tushare_client=FakeTushareStockClient(),
    )
    assert result["vendor_version"] != result["daily_vendor_version"]  # 分叉前提

    landed_count = verify_choice_stock_daily_observation_landing(
        duckdb_path=duckdb_path,
        history_result=result,
        report_date="2026-04-28",
    )
    assert landed_count > 0

    manifest = build_choice_stock_observation_manifest(
        history_result=result,
        refresh_run_id="refresh-run-1",
        report_date="2026-04-28",
        daily_observation_row_count=landed_count,
    )
    assert manifest["vendor_version"] == result["daily_vendor_version"]

    observation = resolve_latest_committed_choice_stock_observation(
        duckdb_path=duckdb_path,
        expected_report_date="2026-04-28",
    )
    assert observation.vendor_version == result["daily_vendor_version"]
    assert observation.materialization_run_id == result["run_id"]
    assert observation.daily_observation_row_count == landed_count


def test_manifest_verification_falls_back_to_run_vendor_for_legacy_payload(tmp_path: Path) -> None:
    """⑤向后兼容:旧 payload 无 daily_vendor_version 键时回退 run 级 vendor。"""

    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)

    result = materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=FakeChoiceStockClient(),
        tushare_client=FakeTushareStockClient(),
    )
    # 全 native run:run 级与 daily 级 vendor 一致;剥掉新键模拟旧 payload
    legacy_payload = {key: value for key, value in result.items() if key != "daily_vendor_version"}
    assert "daily_vendor_version" not in legacy_payload

    landed_count = verify_choice_stock_daily_observation_landing(
        duckdb_path=duckdb_path,
        history_result=legacy_payload,
        report_date="2026-04-28",
    )
    assert landed_count > 0
    manifest = build_choice_stock_observation_manifest(
        history_result=legacy_payload,
        refresh_run_id="refresh-run-legacy",
        report_date="2026-04-28",
        daily_observation_row_count=landed_count,
    )
    assert manifest["vendor_version"] == result["vendor_version"]


def test_vendor_whitelist_assertion_shared_helper() -> None:
    """⑤共享白名单断言:已知三种模式放行,未知/空白 fail-loud。"""

    assert_known_choice_stock_daily_vendor_version("vv_choice_stock_20260811_258c140f3265")
    assert_known_choice_stock_daily_vendor_version("vv_choice_tushare_stock_20251205_43e02a042578")
    assert_known_choice_stock_daily_vendor_version("vv_livermore_supplement_tushare_sina_20260622_2879311a6e15")
    with pytest.raises(ChoiceStockUnknownVendorVersionError, match="generation whitelist"):
        assert_known_choice_stock_daily_vendor_version("vv_wind_stock_20270101_abc")
    with pytest.raises(ChoiceStockUnknownVendorVersionError):
        assert_known_choice_stock_daily_vendor_version("   ")


class _FakeTusharePro:
    """supplement 脚本所需的最小 Tushare pro 接口。"""

    def __init__(self, trade_date_compact: str) -> None:
        self._trade_date = trade_date_compact

    def trade_cal(self, **_kwargs: object) -> pd.DataFrame:
        return pd.DataFrame([{"cal_date": self._trade_date, "is_open": 1}])

    def daily(self, **_kwargs: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": self._trade_date,
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.5,
                    "close": 10.5,
                    "pre_close": 10.0,
                    "pct_chg": 5.0,
                    "vol": 1000.0,
                    "amount": 1050.0,
                }
            ]
        )

    def stk_limit(self, **_kwargs: object) -> pd.DataFrame:
        return pd.DataFrame([{"ts_code": "000001.SZ", "up_limit": 11.0, "down_limit": 9.0}])


def _seed_supplement_source(module: Any, duckdb_path: Path, *, source_date: str) -> None:
    conn = duckdb.connect(str(duckdb_path))
    try:
        module._ensure_schemas(conn)
        conn.execute(
            "insert into choice_stock_universe values (?, '000001.SZ', '平安银行', 'a_share_universe_sector_001004', 'sv_prev', 'vv_choice_stock_20260622_0123456789ab', 'rv', 'prev-run')",
            [source_date],
        )
        conn.execute(
            "insert into choice_stock_sector_membership values (?, '000001.SZ', '银行', '801780', 'sw2021_industry_membership', 'sv_prev', 'vv_choice_stock_20260622_0123456789ab', 'rv', 'prev-run')",
            [source_date],
        )
        conn.execute(
            "insert into fact_choice_macro_daily values ('CA.CSI300_PE', 'CSI300 PE', ?, 12.5, 'daily', 'x', 'sv_prev', 'vv_prev', 'rv', 'ok', 'prev-run')",
            [source_date],
        )
        conn.execute(
            "insert into choice_stock_factor_snapshot values (?, '000001.SZ', 8.0, 1.1, 2.0, 12.0, 30.0, 0.1, 0.2, 0.3, 3.5, '银行', 'sv_prev', 'vv_choice_tushare_stock_factor_20260622_0123456789ab', 'rv', 'prev-run')",
            [source_date],
        )
    finally:
        conn.close()


def test_supplement_script_rejects_native_era_write_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⑤supplement 脚本:tushare 口径 vendor 补写 native 代际日期默认 fail-loud。"""

    module = load_module(
        "scripts.supplement_livermore_after_close_inputs",
        "scripts/supplement_livermore_after_close_inputs.py",
    )
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_supplement_source(module, duckdb_path, source_date="2026-06-22")

    monkeypatch.setattr(module, "resolve_tushare_token_with_settings_fallback", lambda _settings: "token")
    monkeypatch.setattr(
        module,
        "import_tushare_pro",
        lambda: SimpleNamespace(pro_api=lambda _token: _FakeTusharePro("20260623")),
    )
    monkeypatch.setattr(
        module,
        "_fetch_sina_csi300_snapshot",
        lambda: {"close": 4000.0, "pct_chg": 0.5},
    )

    with pytest.raises(ChoiceStockVendorEraViolationError, match="choice_native era"):
        module.supplement_livermore_after_close_inputs(
            duckdb_path=duckdb_path,
            target_date="2026-06-23",
        )
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        count = conn.execute(
            "select count(*) from choice_stock_daily_observation where trade_date = '2026-06-23'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0  # 守卫在事务开始前拦截,未写入任何行

    result = module.supplement_livermore_after_close_inputs(
        duckdb_path=duckdb_path,
        target_date="2026-06-23",
        allow_cross_era_backfill=True,
    )
    assert result["status"] == "completed"
    vendor = str(result["vendor_version"])
    assert vendor.startswith("vv_livermore_supplement_tushare_sina_20260623_")
    assert_known_choice_stock_daily_vendor_version(vendor)  # 白名单命中
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            "select distinct vendor_version from choice_stock_daily_observation where trade_date = '2026-06-23'"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [(vendor,)]
