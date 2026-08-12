from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core_finance.zqtz_asset_bond_category import ZQTZ_ASSET_BOND_ROWS


def _label_by_sort_order() -> dict[int, str]:
    return {int(row["sort_order"]): str(row["row_label"]) for row in ZQTZ_ASSET_BOND_ROWS}


def build_fixture() -> dict[str, object]:
    labels = _label_by_sort_order()
    return {
        "source": "backend/app/core_finance/zqtz_asset_bond_category.py",
        "sort_order_range": [83, 88],
        "parents": {
            labels[82]: [labels[83], labels[84]],
            labels[84]: [labels[85], labels[86], labels[87], labels[88]],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export frontend ADB average rollup fixture from ZQTZ categories.")
    parser.add_argument("--output", type=Path, help="Fixture path to write. Prints JSON when omitted.")
    args = parser.parse_args()

    text = json.dumps(build_fixture(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
