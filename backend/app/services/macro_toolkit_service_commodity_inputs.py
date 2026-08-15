"""商品期货落库状态输入辅助（覆盖率 / 南华输入）。

代码自 macro_toolkit_service.py 门面拆分逐字迁入；语义与行为不变。
"""

from __future__ import annotations

import duckdb


DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS = ("RB", "I", "CU", "AL", "SC", "AU", "NHCI")


def _commodity_futures_coverage(products: list[dict[str, object]]) -> dict[str, object]:
    available_products = [
        str(item["product_code"])
        for item in products
        if str(item.get("product_code") or "") in DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS
        and int(item.get("row_count") or 0) > 0
    ]
    return {
        "target_product_count": len(DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS),
        "available_product_count": len(available_products),
        "available_products": available_products,
        "missing_products": [
            product for product in DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS if product not in set(available_products)
        ],
        "products": products,
    }


def _commodity_futures_missing_nanhua(status: str) -> dict[str, object]:
    return {
        "status": status,
        "product_code": "NHCI",
        "series_id": "NH0100.NHF",
        "system_series_id": "NHCI.NH",
        "latest_trade_date": None,
        "latest_value": None,
        "row_count": 0,
        "source_version": None,
        "vendor_version": None,
        "rule_version": None,
    }


def _normalize_commodity_trade_date(value: object) -> str | None:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10:
        return text[:10]
    return text or None


def _commodity_futures_nanhua_input(conn: duckdb.DuckDBPyConnection) -> dict[str, object]:
    row = conn.execute(
        """
        with normalized as (
          select
            trade_date,
            close_value,
            source_version,
            vendor_version,
            rule_version,
            case
              when regexp_matches(cast(trade_date as varchar), '^[0-9]{8}$')
                then try_strptime(cast(trade_date as varchar), '%Y%m%d')::date
              else try_cast(left(cast(trade_date as varchar), 10) as date)
            end as normalized_trade_date
          from fact_commodity_futures_daily
          where product_code = 'NHCI'
        )
        select trade_date, close_value, count(*) over () as row_count, source_version, vendor_version, rule_version
        from normalized
        order by normalized_trade_date desc nulls last, trade_date desc
        limit 1
        """
    ).fetchone()
    if not row:
        return _commodity_futures_missing_nanhua("missing")
    trade_date, latest_value, row_count, source_version, vendor_version, rule_version = row
    return {
        "status": "hit",
        "product_code": "NHCI",
        "series_id": "NH0100.NHF",
        "system_series_id": "NHCI.NH",
        "latest_trade_date": _normalize_commodity_trade_date(trade_date),
        "latest_value": float(latest_value) if latest_value is not None else None,
        "row_count": int(row_count or 0),
        "source_version": str(source_version) if source_version is not None else None,
        "vendor_version": str(vendor_version) if vendor_version is not None else None,
        "rule_version": str(rule_version) if rule_version is not None else None,
    }
