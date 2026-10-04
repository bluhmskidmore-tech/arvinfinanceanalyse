from __future__ import annotations

from datetime import date, timedelta

CFETS_2026_NOTICE_URL = "https://www.chinamoney.com.cn/chinese/rdgz/20251218/3254567.html"

_DEFAULT_WEEKEND_DAYS = frozenset({5, 6})


def _date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


# 中国法定节假日（国务院办公厅年度放假通知；含落在周末的假日，周末本就非业务日，无害）。
# 2024: 国办发明电〔2023〕7号；2025: 国办发明电〔2024〕8号；2026: 国办发明电〔2025〕7号。
# 人民币中间价发布日不随外币清算假日或国内调休补班日改变。
_CNY_HOLIDAYS: frozenset[date] = frozenset(
    [
        # 2024
        date(2024, 1, 1),
        *_date_range(date(2024, 2, 10), date(2024, 2, 17)),
        *_date_range(date(2024, 4, 4), date(2024, 4, 6)),
        *_date_range(date(2024, 5, 1), date(2024, 5, 5)),
        *_date_range(date(2024, 6, 8), date(2024, 6, 10)),
        *_date_range(date(2024, 9, 15), date(2024, 9, 17)),
        *_date_range(date(2024, 10, 1), date(2024, 10, 7)),
        # 2025
        date(2025, 1, 1),
        *_date_range(date(2025, 1, 28), date(2025, 2, 4)),
        *_date_range(date(2025, 4, 4), date(2025, 4, 6)),
        *_date_range(date(2025, 5, 1), date(2025, 5, 5)),
        *_date_range(date(2025, 5, 31), date(2025, 6, 2)),
        *_date_range(date(2025, 10, 1), date(2025, 10, 8)),
        # 2026
        *_date_range(date(2026, 1, 1), date(2026, 1, 3)),
        *_date_range(date(2026, 2, 15), date(2026, 2, 23)),
        *_date_range(date(2026, 4, 4), date(2026, 4, 6)),
        *_date_range(date(2026, 5, 1), date(2026, 5, 5)),
        *_date_range(date(2026, 6, 19), date(2026, 6, 21)),
        *_date_range(date(2026, 9, 25), date(2026, 9, 27)),
        *_date_range(date(2026, 10, 1), date(2026, 10, 7)),
    ]
)

# 假日数据覆盖的年份。覆盖范围之外的工作日无法判定是否假日，必须 fail-loud，
# 防止 2026-06-10 审计 / 2026-07-19 审计共享 H-3 指出的"下一个未登记假日
# 让正式 FX 物化静默断裂或误放行"。新年份的官方放假通知发布后在此登记。
_CFETS_CALENDAR_COVERED_YEARS = frozenset({2024, 2025, 2026})


def is_cfets_fx_non_business_day(
    target_date: date | str,
    *,
    base_currency: str,
    quote_currency: str,
) -> bool:
    """Return whether CFETS does not publish the RMB middle-rate fixing.

    Currency arguments retain the existing call contract. They do not select a
    settlement calendar: e.g. USD settlement closed on 2026-01-19 while CFETS
    published that day's USD/CNY fixing. All RMB middle-rate pairs share this
    publication calendar.
    """
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)

    if target_date.weekday() in _DEFAULT_WEEKEND_DAYS:
        return True

    if target_date.year not in _CFETS_CALENDAR_COVERED_YEARS:
        raise ValueError(
            f"CFETS holiday calendar does not cover year {target_date.year}; "
            "register the official holiday schedule in "
            "backend/app/core_finance/fx_calendar.py before processing "
            f"target_date={target_date.isoformat()}."
        )
    return target_date in _CNY_HOLIDAYS


__all__ = ["CFETS_2026_NOTICE_URL", "is_cfets_fx_non_business_day"]
