# Macro Toolkit Freshness Refresh Go-live Checklist

Owner: local-dev (arvin)
Rollback: Disable Windows task `MOSS-MacroToolkitFreshness` (`schtasks /Delete /TN MOSS-MacroToolkitFreshness /F`) and alert owner; do not delete DuckDB history rows.

- [x] Approved timer host and service identity recorded in the enablement packet.
- [x] Tushare credential is available to the worker without being copied into this document.
- [x] Single-writer DuckDB window is confirmed (host-local 06:30 ≈ Asia/Shanghai 18:30 on UTC-4; avoid overlapping commodity/choice writers).
- [x] `--dry-run` completed successfully.
- [ ] Pre-enable gate reports `ready`: `python scripts/macro_toolkit_freshness_refresh_timer_preflight.py --stage pre-enable`.
- [ ] Shadow `--run-once --run-kind shadow` completed in the approved test environment (`success` or acceptable `degraded` with CFFEX warning only).
- [ ] Local Windows task `MOSS-MacroToolkitFreshness` installed/updated so the wrapper writes a scheduled receipt (`--run-once --run-kind scheduled --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.json`).
- [ ] First scheduled fire produced a durable receipt with `run_kind=scheduled`, `invocation_mode=run_once`, `source_version=macro_toolkit_freshness_refresh_v3`, and exit code 0.
- [ ] Post-enable gate reports `ready` or `ready_with_warning`: `python scripts/macro_toolkit_freshness_refresh_timer_preflight.py --stage post-enable`.
- [ ] Post-run SQL / receipt `latest_observation_dates` confirms commodity / CSI / NHCI / Choice `EMM00088132` / NCD.SHIBOR / CFFEX max trade dates advanced or already current.
- [ ] First scheduled run evidence is recorded in the handoff status file from the receipt (not from a shadow or enqueue acknowledgement).
