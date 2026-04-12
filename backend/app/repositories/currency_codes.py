from __future__ import annotations


def normalize_currency_code(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = raw.upper()
    mapping = {
        "人民币": "CNY",
        "CNY": "CNY",
        "美元": "USD",
        "USD": "USD",
        "综本": "CNX",
        "CNX": "CNX",
    }
    return mapping.get(raw, mapping.get(normalized, raw))
