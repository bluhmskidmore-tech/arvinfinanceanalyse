# Macro Toolkit Freshness Refresh Timer Enablement Packet

Timer host: local Windows host (F:\MOSS-V3)
Write window: daily 06:30 host-local on UTC-4 (= 18:30 Asia/Shanghai); single-writer DuckDB
Log path: F:\MOSS-V3\data\logs\macro_toolkit_freshness_refresh.log
Receipt path: F:\MOSS-V3\data\logs\macro_toolkit_freshness_refresh_receipt.json

Approved local timer command (no Dramatiq worker required):

```text
python scripts/macro_toolkit_freshness_refresh.py --run-once --run-kind scheduled --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.json
```

Approved production enqueue command (requires Dramatiq broker + worker):

```text
python scripts/macro_toolkit_freshness_refresh.py --enqueue --run-kind scheduled --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.json
```

Note: `--enqueue` only writes a queued acknowledgement receipt. The Dramatiq actor
does not currently persist a completed scheduled receipt. Post-enable evidence must
come from a completed `--run-once --run-kind scheduled` receipt (local timer path or
manual capture after the worker finishes). Do not treat a queued acknowledgement as
first-run proof.

Synchronous shadow validation (before enablement; not post-enable evidence):

```text
python scripts/macro_toolkit_freshness_refresh.py --run-once --run-kind shadow --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.shadow.json
```

Fail-closed gates:

```text
python scripts/macro_toolkit_freshness_refresh_timer_preflight.py --stage pre-enable
python scripts/macro_toolkit_freshness_refresh_timer_preflight.py --stage post-enable --receipt-path data/logs/macro_toolkit_freshness_refresh_receipt.json
```

Keep this job outside other DuckDB write windows. Capture exit status, `run_id`,
step receipts, and `latest_observation_dates` for commodity / CSI / NHCI /
Choice `EMM00088132` / NCD.SHIBOR / CFFEX tables.

This packet deliberately does not install or enable a scheduler. Operations must
use the approved host-specific mechanism (optional local helper:
`scripts/install_macro_toolkit_freshness_timer.ps1`) after pre-enable reports
`ready`.
