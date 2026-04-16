from __future__ import annotations


_CURRENCY_CODE_MAPPING = {
    "人民币": "CNY",
    "CNY": "CNY",
    "美元": "USD",
    "USD": "USD",
    "综本": "CNX",
    "CNX": "CNX",
    "欧元": "EUR",
    "EUR": "EUR",
    "澳元": "AUD",
    "AUD": "AUD",
    "加拿大元": "CAD",
    "CAD": "CAD",
    "港元": "HKD",
    "HKD": "HKD",
    "英镑": "GBP",
    "GBP": "GBP",
    "日元": "JPY",
    "JPY": "JPY",
    "新西兰元": "NZD",
    "NZD": "NZD",
    "新加坡元": "SGD",
    "SGD": "SGD",
    "瑞士法郎": "CHF",
    "CHF": "CHF",
    "俄罗斯卢布": "RUB",
    "卢布": "RUB",
    "RUB": "RUB",
    "韩元": "KRW",
    "KRW": "KRW",
    "南非兰特": "ZAR",
    "兰特": "ZAR",
    "ZAR": "ZAR",
    "阿联酋迪拉姆": "AED",
    "AED": "AED",
    "沙特里亚尔": "SAR",
    "SAR": "SAR",
}


def normalize_currency_code(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = raw.upper()
    return _CURRENCY_CODE_MAPPING.get(raw, _CURRENCY_CODE_MAPPING.get(normalized, normalized))
