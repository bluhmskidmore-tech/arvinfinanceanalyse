from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ProbeResult:
    name: str
    url: str
    status: int | str
    outcome: str
    detail: str | None = None
    result_kind: str | None = None
    basis: str | None = None
    report_dates: list[str] | None = None


def _safe_json_loads(raw: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _payload_detail(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    detail = payload.get("detail")
    return str(detail) if detail is not None else None


def _payload_result_kind(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    meta = payload.get("result_meta")
    if not isinstance(meta, dict):
        return None
    value = meta.get("result_kind")
    return str(value) if value is not None else None


def _payload_basis(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    meta = payload.get("result_meta")
    if not isinstance(meta, dict):
        return None
    value = meta.get("basis")
    return str(value) if value is not None else None


def _payload_report_dates(payload: dict[str, Any] | None) -> list[str] | None:
    if not payload:
        return None
    result_obj = payload.get("result")
    if not isinstance(result_obj, dict):
        return None
    dates = result_obj.get("report_dates")
    if not isinstance(dates, list):
        return None
    return [str(item) for item in dates if item]


def _fetch_json(url: str, timeout_seconds: int = 20) -> ProbeResult:
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
            payload = _safe_json_loads(body)
            return ProbeResult(
                name="",
                url=url,
                status=response.status,
                outcome="pass" if response.status == 200 else "warn",
                detail=_payload_detail(payload),
                result_kind=_payload_result_kind(payload),
                basis=_payload_basis(payload),
                report_dates=_payload_report_dates(payload),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        payload = _safe_json_loads(body)
        return ProbeResult(
            name="",
            url=url,
            status=exc.code,
            outcome="blocked",
            detail=_payload_detail(payload) or body,
            result_kind=_payload_result_kind(payload),
            basis=_payload_basis(payload),
            report_dates=_payload_report_dates(payload),
        )
    except Exception as exc:
        return ProbeResult(
            name="",
            url=url,
            status="ERR",
            outcome="blocked",
            detail=str(exc),
        )


def _named_probe(
    name: str,
    url: str,
    *,
    allowed_statuses: tuple[int, ...] = (200,),
) -> ProbeResult:
    result = _fetch_json(url)
    result.name = name
    if isinstance(result.status, int) and result.status in allowed_statuses:
        result.outcome = "pass"
    else:
        result.outcome = "blocked"
    return result


def _skipped_probe(name: str, url: str, detail: str) -> ProbeResult:
    return ProbeResult(
        name=name,
        url=url,
        status="SKIP",
        outcome="skipped",
        detail=detail,
    )


def build_preflight_report(*, api_base: str, frontend_base: str) -> dict[str, Any]:
    probes: list[ProbeResult] = []

    health = _named_probe("health", f"{api_base}/health")
    probes.append(health)
    probes.append(_named_probe("frontend_root", f"{frontend_base}/"))

    bond_dates = _named_probe("bond_dates", f"{api_base}/api/bond-analytics/dates")
    probes.append(bond_dates)
    bond_report_dates = bond_dates.report_dates or []
    if bond_report_dates:
        probes.append(
            _named_probe(
                "bond_return_decomposition",
                (
                    f"{api_base}/api/bond-analytics/return-decomposition"
                    f"?report_date={bond_report_dates[0]}&period_type=MoM&asset_class=all&accounting_class=all"
                ),
            )
        )
    else:
        probes.append(
            _skipped_probe(
                "bond_return_decomposition",
                f"{api_base}/api/bond-analytics/return-decomposition",
                "Skipped because bond analytics dates are unavailable.",
            )
        )

    risk_dates = _named_probe("risk_dates", f"{api_base}/api/risk/tensor/dates")
    probes.append(risk_dates)
    risk_report_dates = risk_dates.report_dates or []
    if risk_report_dates:
        probes.append(
            _named_probe(
                "risk_tensor",
                f"{api_base}/api/risk/tensor?report_date={risk_report_dates[0]}",
            )
        )
    else:
        probes.append(
            _skipped_probe(
                "risk_tensor",
                f"{api_base}/api/risk/tensor",
                "Skipped because risk tensor dates are unavailable.",
            )
        )

    balance_dates = _named_probe("balance_dates", f"{api_base}/ui/balance-analysis/dates")
    probes.append(balance_dates)
    balance_report_dates = balance_dates.report_dates or []
    if balance_report_dates:
        probes.append(
            _named_probe(
                "balance_overview",
                (
                    f"{api_base}/ui/balance-analysis/overview"
                    f"?report_date={balance_report_dates[0]}&position_scope=all&currency_basis=CNY"
                ),
            )
        )
    else:
        probes.append(
            _skipped_probe(
                "balance_overview",
                f"{api_base}/ui/balance-analysis/overview",
                "Skipped because balance-analysis dates are unavailable.",
            )
        )

    pnl_dates = _named_probe("pnl_dates", f"{api_base}/api/pnl/dates")
    probes.append(pnl_dates)
    pnl_report_dates = pnl_dates.report_dates or []
    if pnl_report_dates:
        report_date = pnl_report_dates[0]
        probes.append(
            _named_probe(
                "pnl_overview",
                f"{api_base}/api/pnl/overview?report_date={report_date}",
            )
        )
        probes.append(
            _named_probe(
                "pnl_bridge",
                f"{api_base}/api/pnl/bridge?report_date={report_date}",
            )
        )
        probes.append(
            _named_probe(
                "executive_pnl_attribution",
                f"{api_base}/ui/pnl/attribution?report_date={report_date}",
            )
        )
    else:
        probes.append(
            _skipped_probe(
                "pnl_overview",
                f"{api_base}/api/pnl/overview",
                "Skipped because pnl dates are unavailable.",
            )
        )
        probes.append(
            _skipped_probe(
                "pnl_bridge",
                f"{api_base}/api/pnl/bridge",
                "Skipped because pnl dates are unavailable.",
            )
        )
        probes.append(
            _skipped_probe(
                "executive_pnl_attribution",
                f"{api_base}/ui/pnl/attribution",
                "Skipped because pnl dates are unavailable.",
            )
        )

    product_category_dates = _named_probe(
        "product_category_dates",
        f"{api_base}/ui/pnl/product-category/dates",
    )
    probes.append(product_category_dates)
    product_category_report_dates = product_category_dates.report_dates or []
    if product_category_report_dates:
        probes.append(
            _named_probe(
                "product_category_monthly",
                (
                    f"{api_base}/ui/pnl/product-category"
                    f"?report_date={product_category_report_dates[0]}&view=monthly"
                ),
            )
        )
    else:
        probes.append(
            _skipped_probe(
                "product_category_monthly",
                f"{api_base}/ui/pnl/product-category",
                "Skipped because product-category dates are unavailable.",
            )
        )

    probes.append(_named_probe("executive_overview", f"{api_base}/ui/home/overview"))
    probes.append(_named_probe("executive_summary", f"{api_base}/ui/home/summary"))

    probes.append(
        _named_probe(
            "ui_risk_overview",
            f"{api_base}/ui/risk/overview",
            allowed_statuses=(503,),
        )
    )
    probes.append(
        _named_probe(
            "ui_home_alerts",
            f"{api_base}/ui/home/alerts",
            allowed_statuses=(503,),
        )
    )
    probes.append(
        _named_probe(
            "ui_home_contribution",
            f"{api_base}/ui/home/contribution",
            allowed_statuses=(503,),
        )
    )

    reserved_report_date = risk_report_dates[0] if risk_report_dates else "2025-12-31"
    reserved_year = reserved_report_date[:4]
    probes.append(
        _named_probe(
            "api_cube_dimensions_reserved",
            f"{api_base}/api/cube/dimensions/bond_analytics",
            allowed_statuses=(503,),
        )
    )
    probes.append(
        _named_probe(
            "api_risk_buckets_reserved",
            f"{api_base}/api/risk/buckets?report_date={reserved_report_date}",
            allowed_statuses=(503,),
        )
    )
    probes.append(
        _named_probe(
            "api_yield_metrics_reserved",
            f"{api_base}/api/analysis/yield_metrics?report_date={reserved_report_date}",
            allowed_statuses=(503,),
        )
    )
    probes.append(
        _named_probe(
            "api_liabilities_counterparty_reserved",
            (
                f"{api_base}/api/analysis/liabilities/counterparty"
                f"?report_date={reserved_report_date}&top_n=10"
            ),
            allowed_statuses=(503,),
        )
    )
    probes.append(
        _named_probe(
            "api_liabilities_monthly_reserved",
            f"{api_base}/api/liabilities/monthly?year={reserved_year}",
            allowed_statuses=(503,),
        )
    )

    outcome_counts = {
        "pass": sum(1 for probe in probes if probe.outcome == "pass"),
        "blocked": sum(1 for probe in probes if probe.outcome == "blocked"),
        "skipped": sum(1 for probe in probes if probe.outcome == "skipped"),
    }
    required_failures = [
        probe.name
        for probe in probes
        if probe.outcome in {"blocked", "skipped"}
    ]
    verdict = "pass" if not required_failures else "blocked"

    return {
        "verdict": verdict,
        "api_base": api_base,
        "frontend_base": frontend_base,
        "summary": outcome_counts,
        "required_failures": required_failures,
        "probes": [asdict(probe) for probe in probes],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:7888")
    parser.add_argument("--frontend-base", default="http://127.0.0.1:5888")
    args = parser.parse_args()

    report = build_preflight_report(
        api_base=args.api_base.rstrip("/"),
        frontend_base=args.frontend_base.rstrip("/"),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
