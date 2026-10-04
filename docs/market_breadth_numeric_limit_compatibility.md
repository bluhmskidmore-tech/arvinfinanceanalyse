# Tushare 数值涨停价与市场封板质量

`rv_market_breadth_daily_v4` 修复了 Tushare 数值 `HIGHLIMIT` 被当成 Choice 是/否标志、因而全日不可分类的问题。Choice 标志和派生涨停价分支保持原有行为；Tushare 分支使用落库实际涨停价，不根据股票板块或 ST 名称猜测价格。

任务按 `trade_date + stock_code` 左联 `stock_limit_price_daily`。观察来源必须是 `vv_choice_tushare_stock_YYYYMMDD_12hex` 或 `vv_livermore_supplement_tushare_sina_YYYYMMDD_12hex`，价格来源必须是 `vv_tushare_stk_limit_YYYYMMDD_12hex`，来源日期均须等于观察日期。观察中的数值 `HIGHLIMIT` 与独立表 `up_limit` 都须有限且为正，两者差值不得超过既有 0.005 元容差。任一条件缺失或冲突时，该股保留为 `unclassified`，不会转成“否”或进入 Choice 派生分支。

`core_finance.market_breadth.classify_limit_touch` 执行实际最高价、收盘价与涨停价的比较。价格非有限、非正或收盘价高于最高价超过容差时不可分类；最高价或收盘价高于涨停价超过容差时计入 `out_of_band`；其余分为封板、炸板和未触板。裸数值标志不能自行启用此分支，必须携带已经验证的数值来源字段。

市场质量仍为 `sealed > broken`；封板与炸板均为零时仍是 `NULL`。全日无可分类输入继续走既有缺失处理，同日已有结果的保留逻辑也未改变。部分覆盖仍沿用原有聚合规则，新增来源、可用价格、不可分类和原因计数供审查，不新增或放宽市场门禁条件。

结果证据中的 `limit_up_basis` 区分 Choice、实际涨停价、混合输入和缺失数值价格。`limit_up_flag_basis_available` 只表示 Choice 分支可分类；新增 `limit_up_price_basis_available` 与 `limit_up_classification_available` 分别表示数值分支和整体可分类。规则版本和落库 vendor 标记同步反映实际使用的来源。

只重算 2026-09-07、2026-09-08 时，使用既有 task 的精确日期参数。以下命令应在持有生产写入窗口的进程中执行；本次修复仅运行隔离 fixture，没有执行生产物化。

```powershell
Set-Location F:\MOSS-V3
.\.venv\Scripts\python.exe -c "from datetime import date; import json; from backend.app.tasks.market_breadth_materialize import materialize_market_breadth_daily; result = materialize_market_breadth_daily(duckdb_path='F:/MOSS-V3/data/moss.duckdb', as_of_date=date(2026, 9, 8), lookback_days=30, recompute_trade_dates=frozenset({date(2026, 9, 7), date(2026, 9, 8)})); print(json.dumps(result, ensure_ascii=False, default=str))"
```

使用默认完整市场覆盖阈值，不传在线 `limit_price_loader`。任务读取已落库的数值涨停价，只写指定两日的市场宽度及门控补充事实。后续市场状态仍须由既有计算链根据实际输入评估。

离线回归覆盖于 `tests/test_limit_up_quality_classification.py` 与 `tests/test_market_breadth_gate_supplement.py`，包括原 Choice 行为、真实价格容差、数值缺失与冲突、来源日期、混合来源、质量三态、指定日期重算及幂等性。
