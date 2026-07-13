from __future__ import annotations

LEDGER_CLASSIFICATION_RULE_VERSION = "rv_ledger_classification_v2"

_ASSET_PAIRS = frozenset(
    {
        ("银行账户", "持有至到期类资产"),
        ("银行账户", "可供出售类资产"),
        ("银行账户", "交易性资产"),
        ("交易账户", "交易性资产"),
        ("银行账户", "应收投资款项"),
    }
)
_LIABILITY_PAIR = ("发行类债券", "发行类债券")


def classify_ledger_direction(
    account_category_std: object,
    asset_class_std: object,
) -> str:
    pair = (str(account_category_std or "__NULL__"), str(asset_class_std or "__NULL__"))
    if pair == _LIABILITY_PAIR:
        return "LIABILITY"
    if pair in _ASSET_PAIRS:
        return "ASSET"
    return "UNCLASSIFIED"
