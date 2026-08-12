from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.repositories.tushare_adapter import TUSHARE_TOKEN_ENV  # noqa: E402
from backend.app.tasks.tushare_stock_disclosure import refresh_stock_official_disclosures  # noqa: E402


def refresh_tushare_stock_disclosures(
    *,
    duckdb_path: str | Path | None,
    stock_codes: list[str],
    from_date: str,
    to_date: str | None,
) -> dict[str, object]:
    kwargs = _actor_kwargs(
        duckdb_path=duckdb_path,
        stock_codes=stock_codes,
        from_date=from_date,
        to_date=to_date,
    )
    return refresh_stock_official_disclosures.fn(**kwargs)


def _actor_kwargs(
    *,
    duckdb_path: str | Path | None,
    stock_codes: list[str],
    from_date: str,
    to_date: str | None,
) -> dict[str, object]:
    resolved_path = Path(duckdb_path) if duckdb_path is not None else get_settings().duckdb_path
    return {
        "duckdb_path": str(resolved_path),
        "stock_codes": _parse_stock_codes(stock_codes),
        "from_date": str(from_date).strip(),
        "to_date": str(to_date).strip() if isinstance(to_date, str) and to_date.strip() else None,
    }


def _parse_stock_codes(values: list[str]) -> list[str]:
    parsed: list[str] = []
    seen: set[str] = set()
    for value in values:
        for chunk in str(value).split(","):
            code = chunk.strip()
            if not code or code in seen:
                continue
            seen.add(code)
            parsed.append(code)
    return parsed


def _sanitize_error_message(message: str) -> str:
    tokens = {os.getenv(TUSHARE_TOKEN_ENV, "").strip()}
    try:
        tokens.add(str(getattr(get_settings(), "tushare_token", "") or "").strip())
    except Exception:  # noqa: S110  # 脱敏辅助不得因 settings 读取失败中断错误上报；env token 兜底已覆盖
        pass
    for token in tokens:
        if token:
            message = message.replace(token, "***")
    return message


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh Tushare official stock disclosures.")
    parser.add_argument("--duckdb-path", default=None)
    parser.add_argument("--stock-code", action="append", required=True, help="Repeatable or comma-separated stock codes.")
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", default=None)
    args = parser.parse_args(argv)

    try:
        result = refresh_tushare_stock_disclosures(
            duckdb_path=args.duckdb_path,
            stock_codes=list(args.stock_code or ()),
            from_date=args.from_date,
            to_date=args.to_date,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": _sanitize_error_message(f"{type(exc).__name__}: {exc}"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
