"""Page-scoped analytical facts. No scores, forecast, or formal metric creation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

RULE_VERSION = "market_funding_rates_observation_v2"
RATE_SLOTS = (
    ("gov_2y", "2年国债", ("EMM00588704",), 2),
    ("gov_5y", "5年国债", ("EMM00166462",), 5),
    ("gov_10y", "10年国债", ("EMM00166466",), 10),
)


def _number(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _date(value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        return None


def _bp(value, previous):
    a, b = _number(value), _number(previous)
    return float((a - b) * 100) if a is not None and b is not None else None


def _row(series, key, label, aliases, allowed, comparison_date=None):
    raw = next((item for alias in aliases for item in series if item.get("series_id") == alias), {})
    observed = _date(raw.get("trade_date"))
    points = {str(p.get("trade_date")): p for p in raw.get("recent_points", [])
              if _date(p.get("trade_date")) and (not observed or str(p["trade_date"]) <= observed)}
    if observed:
        points[observed] = raw
    previous_date = comparison_date or max((d for d in points if observed and d < observed), default=None)
    previous = points.get(previous_date, {})
    value = _number(raw.get("value_numeric"))
    prior = _number(previous.get("value_numeric"))
    fallback = str(raw.get("fallback_mode") or "none")
    note = str(raw.get("policy_note") or "")
    proxy = (key == "shibor_3m" or "not the exact" in note or "proxy" in note.lower()
             or raw.get("vendor_name") == "public_repo_rate_query")
    valid = (allowed and value is not None and observed is not None and raw.get("unit") == "%"
             and raw.get("quality_flag") == "ok" and fallback == "none"
             and not raw.get("is_stale", False) and not (proxy and key == "dr007"))
    previous_valid = (prior is not None and previous.get("quality_flag") == "ok"
                      and previous.get("fallback_mode", "none") == "none"
                      and previous.get("unit", raw.get("unit")) == raw.get("unit")
                      and previous.get("vendor_name", raw.get("vendor_name")) == raw.get("vendor_name")
                      and not previous.get("is_stale", False))
    reason = None if valid else ("来源为代理，不能替代目标指标判断" if proxy and key == "dr007"
                                  else "输入、单位、日期或刷新回执未通过核验")
    return {
        "key": key, "label": "FDR007（DR007代理参考）" if proxy and key == "dr007" else label, "series_id": raw.get("series_id", aliases[0]),
        "value": float(value) if value is not None else None, "unit": raw.get("unit") or "unknown",
        "observation_date": observed, "previous_value": float(prior) if prior is not None else None,
        "previous_date": previous_date, "change_bp": _bp(value, prior) if valid and previous_valid else None,
        "source": raw.get("vendor_name") or raw.get("source_version"),
        "quality_flag": raw.get("quality_flag") or "missing", "fallback_mode": fallback,
        "is_proxy": proxy, "status": "ok" if valid else "unavailable", "reason": reason,
        "recent_points": [{"trade_date": d, "value_numeric": float(_number(p.get("value_numeric")))
                           if _number(p.get("value_numeric")) is not None and p.get("quality_flag") == "ok" else None}
                          for d, p in sorted(points.items())[-20:]],
    }


def _base(rows, allowed, summary, interpretation):
    valid = [r for r in rows if r["status"] == "ok"]
    return {
        "status": "ok" if len(valid) == len(rows) else "degraded" if valid else "unavailable",
        "judgment_allowed": bool(valid) and allowed, "observation_date": rows[0]["observation_date"],
        "comparison_date": rows[0]["previous_date"], "summary": summary,
        "interpretation": interpretation, "limitations": ["按近20期可用观测展示，未证明交易日连续性。"],
        "reason": None if valid else "必要输入及相应刷新回执尚未全部核验，原值仅供核验。",
        "rule_version": RULE_VERSION, "evidence": rows, "rows": rows,
        "verification_route": "/market-overview#market-backend-data-all", "window_label": "近20期",
    }


def _movement(row):
    change = row["change_bp"]
    if change is None:
        return f'{row["label"]}尚无已核验的跨期变化'
    word = "上行" if change > 0 else "回落" if change < 0 else "持平"
    amount = f"{abs(change):.12g} bp" if change else ""
    return f'{row["label"]}较{row["previous_date"]}{word}{amount}'


def build_market_observations(rates_result, *, source_ok, receipt_ready, policy_evidence=None):
    """Only verified input/receipt dependencies permit analytical differences."""
    series = rates_result.get("series", [])
    # Public refresh run IDs and source versions are date-based, so a successful
    # step cannot prove it produced the current facts after a same-day rerun.
    # Until execution-specific evidence exists, a failed receipt blocks all
    # observations; neither a matching alias nor a matching value restores them.
    allowed = source_ok and receipt_ready
    dr = _row(series, "dr007", "DR007", ("CA.DR007", "M002"), allowed)
    shibor = _row(series, "shibor_3m", "SHIBOR 3M", ("NCD.SHIBOR.3M",), allowed)
    funding = _base([dr, shibor], allowed, _movement(dr) + "。" if dr["status"] == "ok" else "资金条件暂不形成判断，保留带日期的原始观测。",
                    "若市场资金价格回落持续传导至实际融资成本，持券融资负担可能下降；本页没有本行融资合同与成本数据，不能量化本行成本变化。SHIBOR 3M仅为期限报价参考。")
    funding["judgment_allowed"] = dr["status"] == "ok"
    policy = policy_evidence or {}
    effective_from, effective_to = _date(policy.get("effective_from")), _date(policy.get("effective_to"))
    policy_valid = (policy.get("validity_status") == "verified" and policy.get("source")
                    and policy.get("unit") == "%" and _number(policy.get("value")) is not None
                    and effective_from and dr["observation_date"] and effective_from <= dr["observation_date"]
                    and (effective_to is None or dr["observation_date"] <= effective_to))
    funding["policy_reference"] = {"value": float(_number(policy.get("value"))) if policy_valid else None,
        "unit": "%", "effective_from": effective_from, "effective_to": effective_to,
        "validity_status": "verified" if policy_valid else "unverified", "source": policy.get("source"),
        "reason": None if policy_valid else "政策基准待核验：操作日利率不能证明后续日期的政策有效区间。"}
    funding["policy_deviation_bp"] = _bp(dr["value"], policy.get("value")) if policy_valid and dr["status"] == "ok" else None
    if funding["policy_deviation_bp"] is not None:
        deviation = funding["policy_deviation_bp"]
        funding["summary"] += f'DR007相对有效政策基准偏离{deviation:+.12g} bp；偏离不自动代表政策松紧。'
    else:
        funding["limitations"].append(funding["policy_reference"]["reason"] or "政策偏离输入未通过核验。")

    rows = [_row(series, key, label, aliases, allowed) | {"tenor_years": tenor}
            for key, label, aliases, tenor in RATE_SLOTS]
    current_date = max((r["observation_date"] for r in rows if r["observation_date"]), default=None)
    # A shared explicit observation date never silently rolls a stale leg forward.
    previous_dates = [r["previous_date"] for r in rows if r["observation_date"] == current_date and r["previous_date"]]
    comparison_date = max(previous_dates, default=None)
    rows = [_row(series, key, label, aliases, allowed, comparison_date) | {"tenor_years": tenor}
            for key, label, aliases, tenor in RATE_SLOTS]
    for row in rows:
        if row["observation_date"] != current_date:
            row.update(status="unavailable", change_bp=None, reason="节点日期与当前曲线观察日不同")
    valid_rows = [r for r in rows if r["status"] == "ok" and r["change_bp"] is not None]
    rates = _base(rows, allowed, "；".join(_movement(r) for r in valid_rows) + "。" if valid_rows else "国债曲线暂不形成跨期判断，保留带日期的原始节点。",
                  "固定利率债价格对收益率变化存在敏感性。组合影响须在明确冲击与风险日期下估算，不能将单一期限变化乘以整个组合DV01；本页不据此判断配置价值或资金因果。")
    rates.update(observation_date=current_date, comparison_date=comparison_date,
                 curve_family="中债国债到期收益率", full_curve_comparison_allowed=len(valid_rows) == 3 and len({r["source"] for r in valid_rows}) == 1,
                 judgment_allowed=bool(valid_rows))
    spreads = []
    for short in rows[:2]:
        long = rows[2]
        valid = (short["status"] == long["status"] == "ok" and short["observation_date"] == long["observation_date"]
                 and short["source"] == long["source"])
        comparison_valid = valid and short["change_bp"] is not None and long["change_bp"] is not None and short["previous_date"] == long["previous_date"]
        value = _bp(long["value"], short["value"]) if valid else None
        previous = _bp(long["previous_value"], short["previous_value"]) if comparison_valid else None
        delta = float(Decimal(str(value)) - Decimal(str(previous))) if previous is not None else None
        spreads.append({"key": f'gov_10y_{short["tenor_years"]}y', "label": f'10年减{short["tenor_years"]}年期限利差',
                        "value_bp": value, "previous_value_bp": previous, "change_bp": delta,
                        "observation_date": current_date, "comparison_date": comparison_date,
                        "status": "ok" if comparison_valid else "unavailable",
                        "reason": None if comparison_valid else "必要节点的日期、来源或两期观测未通过核验", "input_keys": [long["key"], short["key"]]})
        if delta is not None:
            rates["summary"] += f'{spreads[-1]["label"]}{"扩大" if delta > 0 else "收窄" if delta < 0 else "持平"}{f"{abs(delta):.12g} bp" if delta else ""}。'
    rates["spreads"] = spreads
    if not rates["full_curve_comparison_allowed"]:
        rates["limitations"].append("2、5、10年必要节点未全部具备同一期间的有效比较，不能形成三段期限整体判断。")
    return funding, rates
