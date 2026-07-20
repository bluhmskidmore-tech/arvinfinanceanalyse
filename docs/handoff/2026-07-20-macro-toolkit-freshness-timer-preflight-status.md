# Macro Toolkit Freshness Timer Preflight Status (2026-07-20)

Owner: local-dev (arvin)
Rollback: Disable Windows task `MOSS-MacroToolkitFreshness` and stop enqueue; retain DuckDB rows.
Timer host: local Windows host (F:\MOSS-V3)
Write window: daily 06:30 host-local (UTC-4) ≈ 18:30 Asia/Shanghai
Log path: F:\MOSS-V3\data\logs\macro_toolkit_freshness_refresh.log

First scheduled run evidence: shadow `--run-once` 2026-07-20T08:09:21Z run_id=`macro-toolkit-freshness-20260720T080921Z-bdcbd64f` status=`success`; steps commodity=success(row_count=229) headlines=success(row_count=4770) cffex=success(trade_date=2026-07-20,row_count=0 pending vendor); latest_observation_dates commodity=`2026-07-20` CA.CSI300=`2026-07-20` CA.CSI500=`2026-07-20` CA.COPPER=`2026-07-20` NHCI.NH=`2026-07-17` cffex_table=`2026-07-17`.
