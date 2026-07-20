# Macro Toolkit Freshness Refresh Timer Enablement Packet

Timer host: local Windows host (F:\MOSS-V3)
Write window: daily 06:30 host-local on UTC-4 (= 18:30 Asia/Shanghai); single-writer DuckDB
Log path: F:\MOSS-V3\data\logs\macro_toolkit_freshness_refresh.log

Approved timer command:

```text
python scripts/macro_toolkit_freshness_refresh.py --enqueue
```

Synchronous validation (shadow / first enablement only):

```text
python scripts/macro_toolkit_freshness_refresh.py --run-once
```

The scheduler must run from the repository environment with the configured
Dramatiq broker and worker when using `--enqueue`. Keep this job outside other
DuckDB write windows. Capture exit status, message ID (enqueue) or `run_id`
(run-once), step statuses, and latest observation dates for commodity / CSI /
NHCI / Choice `EMM00088132` policy rate / all five `NCD.SHIBOR.*` tenors /
CFFEX tables.

This packet deliberately does not install or enable a scheduler. Operations must
use the approved host-specific mechanism after the preflight reports `ready`.
