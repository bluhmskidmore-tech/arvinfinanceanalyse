# Macro Toolkit Freshness Refresh Go-live Checklist

Owner: local-dev (arvin)
Rollback: Disable Windows task `MOSS-MacroToolkitFreshness` (`schtasks /Delete /TN MOSS-MacroToolkitFreshness /F`) and alert owner; do not delete DuckDB history rows.

- [x] Approved timer host and service identity recorded in the enablement packet.
- [x] Tushare credential is available to the worker without being copied into this document.
- [x] Single-writer DuckDB window is confirmed (host-local 06:30 ≈ Asia/Shanghai 18:30 on UTC-4; avoid overlapping commodity/choice writers).
- [x] `--dry-run` completed successfully.
- [x] `--run-once` completed in the approved test environment and returned `success`.
- [x] Post-run SQL confirms commodity / CSI / NHCI / CFFEX max trade dates advanced or already current.
- [x] First scheduled run evidence is recorded in the handoff status file.
- [x] Local Windows task `MOSS-MacroToolkitFreshness` installed (daily 06:30 host-local, `--run-once` wrapper).
