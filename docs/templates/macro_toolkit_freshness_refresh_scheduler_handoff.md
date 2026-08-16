# Macro Toolkit Freshness Refresh Scheduler Handoff

The repository supplies the freshness actor, CLI, tests, and fail-closed
preflight. Operations owns the external timer and its runtime credentials.

- Actor: `refresh_macro_toolkit_freshness`
- Source version: `macro_toolkit_freshness_refresh_v3`
- Safe review: `python scripts/macro_toolkit_freshness_refresh.py --dry-run`
- Shadow validation: `python scripts/macro_toolkit_freshness_refresh.py --run-once --run-kind shadow --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.shadow.json`
- Local timer invocation (no worker): `python scripts/macro_toolkit_freshness_refresh.py --run-once --run-kind scheduled --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.json`
- Production timer invocation (with worker): `python scripts/macro_toolkit_freshness_refresh.py --enqueue --run-kind scheduled --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.json`
- Pre-enable gate: `python scripts/macro_toolkit_freshness_refresh_timer_preflight.py --stage pre-enable`
- Post-enable gate: `python scripts/macro_toolkit_freshness_refresh_timer_preflight.py --stage post-enable --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.json`

Pipeline (single-writer, sequential):

1. `run_commodity_daily_ingest` (default core products, 14-day lookback) — required
2. `refresh_public_cross_asset_headlines` (CSI300/500, copper CA.*, DR007, …) — required
3. Choice `EMM00088132` 7-day reverse-repo policy rate (45-day rolling window; no carry-forward) — required
4. `refresh_tushare_ncd_shibor_proxy` (NCD.SHIBOR 1M/3M/6M/9M/1Y) — required
5. `materialize_cffex_member_rank` for the latest weekday via `tushare` — optional; soft-fail / weekday fallback

Do not overlap this job with another DuckDB writer. Recommended schedule:
daily at `18:30` in `Asia/Shanghai` (after A-share / commodity settlement).
On a UTC-4 Windows host that is `06:30` host-local.

Treat the first enablement as a shadow run (`--run-kind shadow`). After
enablement, retain the scheduler configuration, durable log path, durable
scheduled receipt, first successful `run_id`, and max observation dates for
`fact_commodity_futures_daily`, `CA.CSI300`, `CA.CSI500`, `CA.COPPER`,
`NHCI.NH`, `EMM00088132`, `NCD.SHIBOR.*`, and `fact_cffex_member_rank_daily`.

Optional local Windows installer
(`scripts/install_macro_toolkit_freshness_timer.ps1`) registers a daily
host-local `06:30` task that runs `--run-once --run-kind scheduled` and writes
`data/logs/macro_toolkit_freshness_refresh_receipt.json`. Production hosts with
a live worker may still enqueue daily work, but post-enable currently requires a
completed `--run-once --run-kind scheduled` receipt — the actor does not yet write
that receipt itself.
