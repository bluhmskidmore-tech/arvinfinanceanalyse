"""Product category account mapping authority.

This module is the canonical product-category mapping source for V3. The
legacy ``backend.app.config.product_category_mapping`` module re-exports this
module to keep older imports working without maintaining a second mapping.
"""

from __future__ import annotations

from decimal import Decimal

DEFAULT_FTP_RATE_PCT = Decimal("1.75")

DERIVATIVE_PNL_ACCOUNTS = [
    "51603010005",
    "51603030002",
    "51603030006",
    "51604010004",
    "51605010001",
    "51701010007",
    "51701030006",
    "51701030008",
    "51701050002",
    "51701070001",
]

INTERMEDIATE_BUSINESS_PNL_ACCOUNTS = [
    "51102000004",
    "51102000005",
    "51104000001",
    "51110000018",
    "51203010001",
    "51203010003",
    "51203070001",
    "51203070002",
    "51203070003",
    "51204000001",
]


def build_default_product_category_config(
    ftp_rate_pct: Decimal = DEFAULT_FTP_RATE_PCT,
) -> list[dict[str, object]]:
    rate = str(ftp_rate_pct)
    return [
        {
            "id": "interbank_lending_assets",
            "name": "拆放同业",
            "side": "asset",
            "level": 0,
            "scale_accounts": ["120", "121"],
            "pnl_accounts": ["50204"],
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "repo_assets",
            "name": "买入返售",
            "side": "asset",
            "level": 0,
            "scale_accounts": ["140", "-14004", "-14005"],
            "pnl_accounts": ["50208", "50210"],
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "bond_investment",
            "name": "债券投资",
            "side": "asset",
            "level": 0,
            "scale_accounts": ["141", "142", "143", "-14301010001", "-14301010002", "144"],
            "pnl_accounts": ["514", "-51401000001", "-51401000002"],
            "ftp_rate_pct": rate,
            "children": [
                "bond_tpl",
                "bond_ac",
                "bond_ac_other",
                "bond_fvoci",
                "bond_valuation_spread",
            ],
        },
        {
            "id": "bond_tpl",
            "name": "TPL",
            "side": "asset",
            "level": 1,
            "scale_accounts": ["141"],
            "pnl_accounts": [
                "51402",
                "51601",
                "51701010001",
                "51701010002",
                "51701010004",
                "51701010006",
            ],
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "bond_ac",
            "name": "AC债券投资",
            "side": "asset",
            "level": 1,
            "scale_accounts": ["142"],
            "pnl_accounts": ["51404"],
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "bond_ac_other",
            "name": "AC其他投资",
            "side": "asset",
            "level": 1,
            "scale_accounts": ["143", "-14301010001", "-14301010002"],
            "pnl_accounts": ["51401", "-51401000001", "-51401000002"],
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "bond_fvoci",
            "name": "FVOCI",
            "side": "asset",
            "level": 1,
            "scale_accounts": ["144"],
            "pnl_accounts": ["51403"],
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "bond_valuation_spread",
            "name": "估值及买卖价差等",
            "side": "asset",
            "level": 1,
            "scale_accounts": [],
            "pnl_accounts": ["51702010001", "51703010001"],
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "interest_earning_assets",
            "name": "生息资产",
            "side": "asset",
            "level": 0,
            "scale_accounts": [
                "120",
                "121",
                "140",
                "-14004",
                "-14005",
                "142",
                "143",
                "-14301010001",
                "-14301010002",
                "144",
            ],
            "pnl_accounts": [
                "50204",
                "50208",
                "50210",
                "51404",
                "51401",
                "-51401000001",
                "-51401000002",
                "51403",
            ],
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "derivatives",
            "name": "衍生品",
            "side": "asset",
            "level": 0,
            "scale_accounts": [],
            "pnl_accounts": DERIVATIVE_PNL_ACCOUNTS,
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "intermediate_business_income",
            "name": "中间业务收入",
            "side": "asset",
            "level": 0,
            "scale_accounts": [],
            "pnl_accounts": INTERMEDIATE_BUSINESS_PNL_ACCOUNTS,
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "interbank_deposits",
            "name": "同业存放",
            "side": "liability",
            "level": 0,
            "scale_accounts": ["234", "235"],
            "pnl_accounts": ["52206"],
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "interbank_borrowings",
            "name": "同业拆入",
            "side": "liability",
            "level": 0,
            "scale_accounts": ["241", "242"],
            "pnl_accounts": ["52204"],
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "repo_liabilities",
            "name": "卖出回购",
            "side": "liability",
            "level": 0,
            "scale_accounts": ["255"],
            "pnl_accounts": ["52208", "52210"],
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "interbank_cds",
            "name": "同业存单",
            "side": "liability",
            "level": 0,
            "scale_accounts": ["27205000001", "27206000001"],
            "pnl_accounts": ["52300030001"],
            "ftp_rate_pct": rate,
            "children": [],
        },
        {
            "id": "credit_linked_notes",
            "name": "信用联结票据",
            "side": "liability",
            "level": 0,
            "scale_accounts": ["24501000004", "24501000005"],
            "pnl_accounts": ["51605010002", "51710020002"],
            "ftp_rate_pct": rate,
            "children": [],
        },
    ]


def format_account_list(accounts: list[str] | tuple[str, ...] | None) -> str:
    if not accounts:
        return "-"
    result: list[str] = []
    for account in accounts:
        if account.startswith("-"):
            result.append(account)
        else:
            result.append(f"+{account}" if result else account)
    return "".join(result)


def _legacy_product_category_config() -> dict[str, list[dict[str, object]]]:
    """Compatibility view for the V2 dict-shaped config."""
    rows = build_default_product_category_config()
    by_id = {str(item["id"]): item for item in rows}
    legacy: dict[str, list[dict[str, object]]] = {"asset": [], "liability": []}
    order_by_side = {"asset": 0, "liability": 0}

    for item in rows:
        if int(item["level"]) != 0:
            continue
        side = str(item["side"])
        order_by_side[side] += 1
        legacy_item: dict[str, object] = {
            "name": item["name"],
            "scale_accounts": item["scale_accounts"],
            "pnl_accounts": item["pnl_accounts"],
            "order": order_by_side[side],
        }
        children = [
            {
                "name": by_id[child_id]["name"],
                "scale_accounts": by_id[child_id]["scale_accounts"],
                "pnl_accounts": by_id[child_id]["pnl_accounts"],
            }
            for child_id in item["children"]
        ]
        if children:
            legacy_item["children"] = children
        legacy[side].append(legacy_item)

    return legacy


PRODUCT_CATEGORY_CONFIG = _legacy_product_category_config()
