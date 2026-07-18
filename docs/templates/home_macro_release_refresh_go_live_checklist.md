# Homepage Macro Release Refresh Go-live Checklist

Owner: <required operations owner>
Rollback: <required disable-and-alert procedure>

- [ ] Approved timer host and service identity recorded in the enablement packet.
- [ ] Tushare credential is available to the worker without being copied into this document.
- [ ] Outbound access is limited to the recorded NBS hosts plus existing Tushare access.
- [ ] Single-writer DuckDB window is confirmed.
- [ ] `--dry-run` completed successfully.
- [ ] `--run-once` completed in the approved test environment and returned `success`.
- [ ] GDP shadow receipt records `run_id`, `release_url`, `content_sha256`, `report_period`, `value`, `nbs.macro.cn_gdp.quarterly` when selected, and `selected_vendor`.
- [ ] Raw and normalized archive paths plus ingest batch ID are retained for lineage review.
- [ ] Homepage/browser evidence confirms CPI, PPI, GDP, and PMI dates and sources.
- [ ] Rollback can disable NBS selection while preserving Tushare fallback.
- [ ] Rollback evidence explicitly says do not delete governed observations or immutable archives.
- [ ] First scheduled run evidence is recorded in the handoff status file.
