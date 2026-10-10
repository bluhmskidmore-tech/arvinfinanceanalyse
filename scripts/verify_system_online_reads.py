"""Read-only, fixed-domain online publication probe; never submits an update.

Wall-clock intervals are retained for correlation with independent writer/CAS
receipts. A caller-supplied phase label is not proof of writer overlap. Output
contains hashes and contract metadata, not financial amounts or source rows.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


GENERATION_HEADER = "X-MOSS-Read-Generation"
VOLATILE_KEYS = frozenset({"computed_at", "generated_at"})


def _canonical_business(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _canonical_business(item)
            for key, item in value.items()
            if key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_canonical_business(item) for item in value]
    return value


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _probe(
    base_url: str, domain: str, path: str, generation: str | None,
    captured_business: dict | None = None,
) -> dict:
    started_at = _now()
    started = time.perf_counter()
    headers = {"Accept": "application/json"}
    if generation:
        headers[GENERATION_HEADER] = generation
    request = Request(base_url + path, headers=headers, method="GET")
    result: dict = {"domain": domain, "path": path, "started_at": started_at}
    try:
        try:
            response = urlopen(request, timeout=60)  # noqa: S310
        except HTTPError as exc:
            response = exc
        with response:
            result["http_status"] = response.status
            result["generation"] = response.headers.get(GENERATION_HEADER)
            body = response.read()
        payload = json.loads(body)
        business = payload.get("result") if isinstance(payload, dict) else None
        result["envelope_valid"] = isinstance(business, dict) and isinstance(
            payload.get("result_meta"), dict
        )
        if domain == "updates" and isinstance(payload, dict):
            dates = payload.get("financial_dates")
            runs = payload.get("runs")
            result["envelope_valid"] = isinstance(dates, list) and isinstance(runs, list)
            business = {"financial_dates": dates}
            result["financial_dates"] = dates
            result["live_run_statuses"] = [
                {key: run.get(key) for key in ("run_id", "report_date", "status")}
                for run in runs if isinstance(run, dict)
            ] if isinstance(runs, list) else []
        if isinstance(business, dict):
            if captured_business is not None:
                captured_business[domain] = business
            encoded = json.dumps(
                _canonical_business(business), sort_keys=True,
                ensure_ascii=False, separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
            result["business_sha256"] = hashlib.sha256(encoded).hexdigest()
            for key in (
                "report_date", "as_of_date", "domains_effective_date",
                "domains_missing", "position_scope", "currency_basis",
                "generation", "result_version", "quality_flag",
            ):
                if key in business:
                    result[f"business_{key}"] = business[key]
        result["file_lock_error"] = any(
            marker in body.lower()
            for marker in (b"could not set lock", b"conflicting lock", b"file is being used")
        )
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        result["error_type"] = type(exc).__name__
    finally:
        result["finished_at"] = _now()
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return result


def _business_tieout(payloads: dict, report_date: str) -> list[dict]:
    """Same-source closure checks, not independent accounting or metric promotion.

    Authority: executive_service overview AUM/DV01 mappings; metric_dictionary
    MTR-BAL-001 and MTR-RSK-001/020/101; get_portfolio_headlines reads the same
    full formal bond partition used by risk_tensor_materialize. No duration or
    PnL total is inferred from similarly named fields with different scopes.
    """
    checks: list[dict] = []
    try:
        home, balance, bond, risk = (payloads[key] for key in ("home", "balance", "bond", "risk"))
        if any(value.get("report_date") != report_date for value in (home, balance, bond, risk)):
            raise ValueError("Dates are not comparable.")
        if home.get("domains_missing") or any(
            value != report_date for value in home.get("domains_effective_date", {}).values()
        ):
            raise ValueError("Home has partial or differently dated components.")
        if balance.get("currency_basis") != "CNY" or balance.get("position_scope") != "all":
            raise ValueError("Balance scope is not the fixed all/CNY sample.")
        metrics = {item["id"]: item for item in home["overview"]["metrics"]}
        if metrics["aum"].get("label") != "总资产规模":
            raise ValueError("Home AUM is a fallback bond-only scope.")

        def numeric(block: dict, unit: str) -> object:
            if block.get("unit") != unit:
                raise ValueError("Numeric unit differs from the established mapping.")
            return block["raw"]

        pairs = [
            ("home_aum_equals_balance_assets", numeric(metrics["aum"]["value"], "yuan"),
             balance["asset_total_market_value_amount"], "0.01"),
            ("home_dv01_equals_bond_dv01", numeric(metrics["dv01"]["value"], "dv01"),
             bond["total_dv01"], "0.01"),
            ("bond_dv01_equals_risk_dv01", bond["total_dv01"],
             numeric(risk["portfolio_dv01"], "dv01"), "0.01"),
            ("bond_market_value_equals_risk_market_value", bond["total_market_value"],
             numeric(risk["total_market_value"], "yuan"), "0.01"),
            ("bond_row_count_equals_risk_row_count", bond["bond_count"], risk["bond_count"], "0"),
        ]
        for name, left, right, tolerance in pairs:
            left_decimal, right_decimal = Decimal(str(left)), Decimal(str(right))
            if not left_decimal.is_finite() or not right_decimal.is_finite():
                raise ValueError("A comparable amount is missing or non-finite.")
            checks.append({
                "check": name,
                "status": "passed" if abs(left_decimal - right_decimal) <= Decimal(tolerance) else "failed",
                "absolute_tolerance": tolerance,
            })
        for field in ("market_value", "amortized_cost", "accrued_interest"):
            total = Decimal(str(balance[f"total_{field}_amount"]))
            sides = sum(Decimal(str(balance[f"{side}_total_{field}_amount"])) for side in ("asset", "liability"))
            if not total.is_finite() or not sides.is_finite():
                raise ValueError("Balance closure contains a missing or non-finite amount.")
            checks.append({
                "check": f"balance_gross_{field}_equals_asset_plus_liability",
                "status": "passed" if abs(total - sides) <= Decimal("0.01") else "failed",
                "absolute_tolerance": "0.01",
            })
    except (KeyError, TypeError, ValueError, InvalidOperation):
        checks.append({"check": "comparable_scope_and_values", "status": "pending"})
    return checks


def _interaction(
    base_url: str, report_date: str, interaction: int, include_update_status: bool = False,
    business_tieout: bool = False,
) -> list[dict]:
    # The first response selects a generation; all other calls in this nominated
    # interaction must request it even if the server pointer changes meanwhile.
    captured_business: dict = {}

    def read(domain: str, path: str, generation: str | None) -> dict:
        if business_tieout:
            return _probe(base_url, domain, path, generation, captured_business)
        return _probe(base_url, domain, path, generation)

    home = read("home", "/ui/home/snapshot", None)
    generation = home.get("generation")
    paths = (
        ("balance", f"/ui/balance-analysis/overview?report_date={report_date}"),
        ("bond", f"/api/bond-analytics/portfolio-headlines?report_date={report_date}"),
        ("risk", f"/api/risk/tensor?report_date={report_date}"),
        ("pnl", f"/api/pnl/by-business-insights?year={report_date[:4]}&as_of_date={report_date}"),
    )
    rows = [home]
    # Each interaction is sequential; concurrent interactions establish the
    # specified outstanding client count without multiplying it by five.
    for domain, path in paths:
        rows.append(read(domain, path, generation))
    if include_update_status:
        rows.append(read("updates", "/api/data-updates", generation))
    if business_tieout:
        home["business_tieout"] = _business_tieout(captured_business, report_date)
    for row in rows:
        row["interaction"] = interaction
        row["requested_generation"] = generation if row is not home else None
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:7888")
    parser.add_argument("--report-date", required=True)
    parser.add_argument("--clients", type=int, choices=(1, 5, 10), default=5)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--require-generation", action="store_true")
    parser.add_argument("--include-update-status", action="store_true")
    parser.add_argument("--business-tieout", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    date.fromisoformat(args.report_date)
    parsed = urlsplit(args.base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("Only an explicitly local HTTP API is allowed.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
        parser.error("base-url must contain only the local API origin.")
    if not 1 <= args.rounds <= 20:
        parser.error("rounds must be between 1 and 20.")
    base_url = args.base_url.rstrip("/")
    rows: list[dict] = []
    for round_index in range(args.rounds):
        with ThreadPoolExecutor(max_workers=args.clients) as pool:
            futures = [
                pool.submit(_interaction, base_url, args.report_date,
                            round_index * args.clients + offset, args.include_update_status,
                            **({"business_tieout": True} if args.business_tieout else {}))
                for offset in range(args.clients)
            ]
            for future in futures:
                for row in future.result():
                    row["round"] = round_index
                    rows.append(row)
    failures: list[dict] = []
    fingerprints: dict[tuple, set] = {}
    timings: dict[str, list[float]] = {}
    for row in rows:
        problems = []
        if row.get("http_status") != 200 or not row.get("envelope_valid"):
            problems.append("http_or_envelope")
        if row.get("file_lock_error"):
            problems.append("file_lock")
        if any(check.get("status") != "passed" for check in row.get("business_tieout", [])):
            problems.append("business_tieout_not_passed")
        if args.require_generation and not row.get("generation"):
            problems.append("missing_generation")
        if row.get("requested_generation") and row.get("generation") != row["requested_generation"]:
            problems.append("mixed_interaction_generation")
        actual_date = row.get("business_as_of_date", row.get("business_report_date"))
        if row["domain"] == "updates":
            dates = row.get("financial_dates") or []
            if {item.get("key") for item in dates} != {"balance", "interbank", "pnl", "bond", "risk"}:
                problems.append("missing_financial_dates")
            if any(item.get("as_of_date") != args.report_date for item in dates):
                problems.append("unexpected_actual_date")
        elif actual_date != args.report_date:
            problems.append("unexpected_actual_date")
        if problems:
            failures.append({"interaction": row["interaction"], "domain": row["domain"], "problems": problems})
        if row.get("business_sha256"):
            fingerprints.setdefault((row["domain"], row.get("generation")), set()).add(row["business_sha256"])
        timings.setdefault(row["domain"], []).append(row["elapsed_ms"])
    consistency = [
        {"domain": domain, "generation": generation, "distinct_business_hashes": len(hashes)}
        for (domain, generation), hashes in fingerprints.items()
    ]
    for group in consistency:
        if group["distinct_business_hashes"] != 1:
            failures.append({**group, "problems": ["business_payload_changed_within_generation"]})
    summary = {
        domain: {"requests": len(values), "p95_ms": sorted(values)[math.ceil(len(values) * 0.95) - 1],
                 "max_ms": max(values)}
        for domain, values in timings.items()
    }
    evidence = {
        "phase_label": args.phase, "clients": args.clients, "rounds": args.rounds,
        "report_date": args.report_date, "require_generation": args.require_generation,
        "include_update_status": args.include_update_status,
        "business_tieout": args.business_tieout,
        "writer_overlap_proven": False,
        "writer_overlap_note": "Correlate request intervals with independent writer/CAS receipts; the phase label is not proof.",
        "hash_excluded_keys": sorted(VOLATILE_KEYS),
        "hash_is_not_independent_accounting_audit": True,
        "summary": summary, "consistency": consistency, "failures": failures, "requests": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "failures": failures, "output": str(args.output)}, ensure_ascii=False))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
