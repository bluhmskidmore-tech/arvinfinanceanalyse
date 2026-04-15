"""
产品类别科目映射（自 MOSS-V2 core_finance/config 迁入）。
"""

PRODUCT_CATEGORY_CONFIG = {
    "asset": [
        {
            "name": "拆放同业",
            "scale_accounts": ["120", "121"],
            "pnl_accounts": ["50204"],
            "order": 1,
        },
        {
            "name": "买入返售证券",
            "scale_accounts": ["140", "-14004", "-14005"],
            "pnl_accounts": ["50208", "50210"],
            "order": 2,
        },
        {
            "name": "债券投资",
            "order": 3,
            "scale_accounts": ["141", "142", "143", "-14301010001", "-14301010002", "144"],
            "pnl_accounts": ["514", "-51401000001", "-51401000002"],
            "children": [
                {
                    "name": "TPL",
                    "scale_accounts": ["141"],
                    "pnl_accounts": [
                        "51402",
                        "51601",
                        "51701010001",
                        "51701010002",
                        "51701010004",
                        "51701010006",
                    ],
                },
                {
                    "name": "AC债券投资",
                    "scale_accounts": ["142"],
                    "pnl_accounts": ["51404"],
                },
                {
                    "name": "AC其他投资",
                    "scale_accounts": ["143", "-14301010001", "-14301010002"],
                    "pnl_accounts": ["51401", "-51401000001", "-51401000002"],
                },
                {
                    "name": "FVOCI",
                    "scale_accounts": ["144"],
                    "pnl_accounts": ["51403"],
                },
                {
                    "name": "估值及买卖价差等",
                    "scale_accounts": [],
                    "pnl_accounts": ["51702010001", "51703010001"],
                },
            ],
        },
        {
            "name": "生息资产",
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
            "order": 4,
        },
        {
            "name": "衍生品",
            "scale_accounts": [],
            "pnl_accounts": [
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
            ],
            "order": 5,
        },
        {
            "name": "中间业务收入",
            "scale_accounts": [],
            "pnl_accounts": [
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
            ],
            "order": 6,
        },
    ],
    "liability": [
        {
            "name": "同业存放",
            "scale_accounts": ["234", "235"],
            "pnl_accounts": ["52206"],
            "order": 1,
        },
        {
            "name": "同业拆入",
            "scale_accounts": ["241", "242"],
            "pnl_accounts": ["52204"],
            "order": 2,
        },
        {
            "name": "卖出回购证券",
            "scale_accounts": ["255"],
            "pnl_accounts": ["52208", "52210"],
            "order": 3,
        },
        {
            "name": "同业存单",
            "scale_accounts": ["27205000001", "27206000001"],
            "pnl_accounts": ["52300030001"],
            "order": 4,
        },
        {
            "name": "信用联结票据",
            "scale_accounts": ["24501000004", "24501000005"],
            "pnl_accounts": ["51605010002", "51710020002"],
            "order": 5,
        },
    ],
}


def format_account_list(accounts):
    if not accounts:
        return "-"
    result = []
    for acc in accounts:
        if acc.startswith("-"):
            result.append(acc)
        else:
            result.append(f"+{acc}" if result else acc)
    return "".join(result)
