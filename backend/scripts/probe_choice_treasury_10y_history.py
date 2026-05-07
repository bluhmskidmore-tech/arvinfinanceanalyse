"""One-off: Choice EDB history depth for treasury par 10Y (EMM00166466).

Run from repo root:
  set PYTHONPATH=<repo> && python backend/scripts/probe_choice_treasury_10y_history.py

Requires Choice (EmQuantAPI) login; uses same code as VendorAdapter._fetch_choice_curve.
"""
from __future__ import annotations

import sys

from backend.app.repositories.akshare_adapter import _choice_rows_from_result, _normalize_record_trade_date
from backend.app.repositories.choice_client import ChoiceClient

CODE = "EMM00166466"
START = "2024-01-02"
END = "2026-05-04"


def main() -> int:
    opts = f"IsLatest=0,StartDate={START},EndDate={END},Ispandas=1"
    raw = ChoiceClient().edb([CODE], opts)
    rows = _choice_rows_from_result(raw)
    by_date: dict[str, object] = {}
    for row in rows:
        if str(row.get("vendor_code") or "") != CODE:
            continue
        td = _normalize_record_trade_date(row.get("trade_date"))
        v = row.get("value")
        if not td or v in (None, ""):
            continue
        by_date[td] = v
    dist = sorted(by_date)
    print("code", CODE, "window", START, "..", END)
    print("parsed_rows", len(rows), "distinct_dates_with_value", len(dist))
    if dist:
        print("min_date", dist[0], "max_date", dist[-1])
    if len(dist) >= 250:
        print("VERDICT: >= 250 trading-ish days with values in this window")
    else:
        print("VERDICT: < 250 distinct days in this window")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FAILED", type(exc).__name__, exc, file=sys.stderr)
        raise SystemExit(3) from exc
