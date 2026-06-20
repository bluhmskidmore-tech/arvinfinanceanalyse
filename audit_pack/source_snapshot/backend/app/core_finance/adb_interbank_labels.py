"""同业 product_type → 展示分类（与 V1 `domain_dictionary` + `adb_service.map_ib_category` 对齐）。"""

from __future__ import annotations

# V1 ASSET_GROUP_拆出存放 = ("拆放", "存放")等 — 不含通配，用子串包含判断
ASSET_GROUP_拆出存放 = ("拆放", "存放")
ASSET_GROUP_买入返售 = ("买入返售",)
LIAB_GROUP_拆入存放 = ("拆入", "存放")
LIAB_GROUP_卖出回购 = ("卖出回购",)


def map_ib_category(product_type: str | None, side: str) -> str:
    t = (product_type or "").strip()
    if side == "Asset":
        if any(k in t for k in ASSET_GROUP_拆出存放):
            return "同业拆出/存放"
        if any(k in t for k in ASSET_GROUP_买入返售):
            return "买入返售"
        return f"同业资产-{t or '其他'}"
    if any(k in t for k in LIAB_GROUP_拆入存放):
        return "同业拆入/存放"
    if any(k in t for k in LIAB_GROUP_卖出回购):
        return "卖出回购"
    return f"同业负债-{t or '其他'}"
