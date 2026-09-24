# Homepage Macro Release Refresh Timer Enablement Packet

Timer host: <required host>
Write window: <required timezone and schedule>
Log path: <required durable log path>

NBS allowed hosts: stats.gov.cn, www.stats.gov.cn
The worker also requires the existing Tushare outbound access for fallback.

Approved timer command:

```text
python scripts/home_macro_release_refresh.py --enqueue
```

The scheduler must run from the repository environment with the configured Dramatiq broker and worker. Keep this job outside other DuckDB write windows. Capture exit status, message ID, actor result, and the four series' latest observation dates.

Enforce a single-writer window for DuckDB. The timer command above is the only
approved scheduler invocation; operators must not substitute a synchronous
write command.

For the first shadow run, retain `run_id`, `release_url`, `content_sha256`,
`report_period`, `value`, selected `series_id` (`nbs.macro.cn_gdp.quarterly`
when NBS wins), `selected_vendor`, ingest batch ID, raw archive path, and
normalized archive path. The receipt must also state whether Tushare was used
as fallback and why.

This packet deliberately does not install or enable a scheduler. Operations must use the approved host-specific mechanism after the preflight reports `ready`.
