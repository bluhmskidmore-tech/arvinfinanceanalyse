from __future__ import annotations

import calendar
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

_NONSTD_PNL_PATTERN = re.compile(
    r"\u975e\u6807(?P<bucket>514|516|517)-(?P<start>\d{8})-(?P<end>\d{4})\.xlsx$",
    re.IGNORECASE,
)
_FI_MONTH_SUFFIX = re.compile(r"FI\u635f\u76ca(?P<ym>\d{6})\.xls$", re.IGNORECASE)


@dataclass(frozen=True)
class SourceFileMetadata:
    source_family: str
    report_date: str | None = None
    report_start_date: str | None = None
    report_end_date: str | None = None
    report_granularity: str | None = None


def detect_source_family(file_name: str) -> str:
    """
    MOSS-SYSTEM-V1 parity (`ingest_daily_data.scan_and_process_files`):
    case-fold ASCII via upper(); Chinese literals unchanged.
    """
    fn_u = file_name.upper()
    if "ZQTZSHOW" in fn_u or "ZQTZ" in fn_u:
        return "zqtz"
    if "TYWLSHOW" in fn_u or "TYWL" in fn_u:
        return "tyw"
    if "FI损益" in file_name or "FI损益" in fn_u:
        return "pnl"
    if "FI" in fn_u:
        return "pnl"
    if "非标517" in file_name:
        return "pnl_517"
    if "非标516" in file_name:
        return "pnl_516"
    if "非标514" in file_name:
        return "pnl_514"
    return "unknown"


def extract_report_date_from_name(file_name: str) -> str | None:
    return describe_source_file(file_name).report_date


def _extract_loose_date_v1(file_name: str) -> str:
    """Ported from V1 `extract_date_from_filename` — last resort is today (local)."""
    match = re.search(r"(\d{8})", file_name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date().isoformat()
        except ValueError:
            pass

    match = re.search(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", file_name)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            pass

    match = re.search(r"(\d{1,2})\.(\d{1,2})", file_name)
    if match:
        month_int, day_int = int(match.group(1)), int(match.group(2))
        try:
            current_year = date.today().year
            return date(current_year, month_int, day_int).isoformat()
        except ValueError:
            pass

    return date.today().isoformat()


def describe_source_file(file_name: str) -> SourceFileMetadata:
    family = detect_source_family(file_name)
    if family == "unknown":
        return SourceFileMetadata(source_family="unknown")

    nonstd_match = _NONSTD_PNL_PATTERN.search(file_name)
    if nonstd_match and family == f"pnl_{nonstd_match.group('bucket')}":
        bucket = nonstd_match.group("bucket")
        start_date = _parse_yyyymmdd(nonstd_match.group("start"))
        end_date = _derive_range_end_date(
            start_date=start_date,
            end_mmdd=nonstd_match.group("end"),
        )
        return SourceFileMetadata(
            source_family=f"pnl_{bucket}",
            report_date=end_date.isoformat(),
            report_start_date=start_date.isoformat(),
            report_end_date=end_date.isoformat(),
            report_granularity="range",
        )

    if family == "pnl":
        month_match = _FI_MONTH_SUFFIX.search(file_name)
        if month_match:
            ym = month_match.group("ym")
            year, month = int(ym[:4]), int(ym[4:6])
            month_end = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
            return SourceFileMetadata(
                source_family="pnl",
                report_date=month_end,
                report_start_date=f"{year:04d}-{month:02d}-01",
                report_end_date=month_end,
                report_granularity="month",
            )

    if family in {"pnl_514", "pnl_516", "pnl_517"} and not nonstd_match:
        rd = _extract_loose_date_v1(file_name)
        return SourceFileMetadata(
            source_family=family,
            report_date=rd,
            report_start_date=rd,
            report_end_date=rd,
            report_granularity="day",
        )

    rd = _extract_loose_date_v1(file_name)
    return SourceFileMetadata(
        source_family=family,
        report_date=rd,
        report_start_date=rd,
        report_end_date=rd,
        report_granularity="day",
    )


def classify_zqtz_preview(row: Mapping[str, object]) -> dict[str, object]:
    business_type_primary = _text(row, "业务种类1")
    instrument_code = _text(row, "债券代号")
    business_type_final = business_type_primary
    trace_fields = ["业务种类1"]

    if business_type_primary == "其他债券":
        prefix_rules = {
            "SA": "公募基金",
            "J0": "资管计划",
            "J1": "美元委外",
            "J3": "结构化融资",
            "J4": "结构化融资",
            "JM": "债权融资计划",
        }
        for prefix, mapped in prefix_rules.items():
            if instrument_code.upper().startswith(prefix):
                business_type_final = mapped
                break
        trace_fields.append("债券代号")

    if business_type_final == "公募基金":
        asset_group = "基金类"
    elif business_type_final in {"资管计划", "债权融资计划", "美元委外", "结构化融资"}:
        asset_group = "特定目的载体及其他非标类"
    else:
        asset_group = "债券类"

    return {
        "business_type_primary": business_type_primary,
        "business_type_final": business_type_final,
        "asset_group": asset_group,
        "manual_review_needed": False,
        "trace_fields": trace_fields,
    }


def classify_tyw_preview(row: Mapping[str, object]) -> dict[str, object]:
    business_type_primary = _text(row, "产品类型")
    investment_portfolio = _text(row, "投资组合")
    cbirc_type = _text(row, "会计类型_银保监会")
    pboc_type = _text(row, "会计类型_人行")
    core_customer_type = _text(row, "核心客户类型")
    account_type = _text(row, "账户类型")
    special_account_type = _text(row, "特殊账户类型")
    custody_account_name = _text(row, "托管账户名称")

    if business_type_primary in {"买入返售证券", "卖出回购证券", "卖出回购票据"}:
        product_group = "回购类"
    elif business_type_primary in {"拆放同业", "同业拆入"}:
        product_group = "拆借类"
    else:
        product_group = "存放类"

    combined_institution = " ".join(item for item in (cbirc_type, pboc_type) if item)
    if "银行类金融机构" in combined_institution:
        institution_category = "bank"
    elif "非银行金融机构" in combined_institution:
        institution_category = "non-bank"
    elif core_customer_type in {"基金", "保险", "信托", "券商", "金融租赁", "消费金融", "汽车金融"}:
        institution_category = "non-bank"
    else:
        institution_category = "unknown"

    if account_type == "清算类" or special_account_type == "托管账户" or custody_account_name:
        special_nature = "托管清算"
    else:
        special_nature = "普通"

    manual_review_needed = False
    if business_type_primary in {"存放同业", "同业拆入", "买入返售证券", "卖出回购证券", "卖出回购票据"}:
        manual_review_needed = institution_category == "non-bank"
    elif business_type_primary == "拆放同业":
        manual_review_needed = institution_category == "bank"
    elif institution_category == "unknown":
        manual_review_needed = True

    return {
        "business_type_primary": business_type_primary,
        "product_group": product_group,
        "institution_category": institution_category,
        "special_nature": special_nature,
        "manual_review_needed": manual_review_needed,
        "trace_fields": [
            "产品类型",
            "投资组合",
            "会计类型_银保监会",
            "会计类型_人行",
            "核心客户类型",
            "账户类型",
            "特殊账户类型",
            "托管账户名称",
        ],
        "investment_portfolio": investment_portfolio,
    }


def classify_pnl_preview(row: Mapping[str, object]) -> dict[str, object]:
    invest_type_raw = _text(row, "投资类型")
    instrument_code = _text(row, "债券代码") or _text(row, "资产代码")
    portfolio_name = _text(row, "投资组合")
    cost_center = _text(row, "成本中心")
    currency = _text(row, "币种")

    return {
        "invest_type_raw": invest_type_raw,
        "instrument_code": instrument_code,
        "portfolio_name": portfolio_name,
        "cost_center": cost_center,
        "currency": currency,
        "manual_review_needed": False,
        "trace_fields": ["投资类型", "债券代码", "成本中心"],
    }


def classify_nonstd_pnl_preview(row: Mapping[str, object], bucket: str) -> dict[str, object]:
    account_code = _text(row, "科目号") or _text(row, "科目代码") or _text(row, "会计科目")
    asset_code = _text(row, "资产代码")
    dc_flag_raw = _text(row, "借贷标识") or _text(row, "方向")
    product_type = _text(row, "产品类型")
    raw_amount = _text(row, "金额") or _text(row, "AMOUNT")

    return {
        "journal_type": bucket,
        "product_type": product_type,
        "asset_code": asset_code,
        "account_code": account_code,
        "dc_flag_raw": dc_flag_raw,
        "raw_amount": raw_amount,
        "manual_review_needed": False,
        "trace_fields": ["科目号", "资产代码", "借贷标识"],
    }


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key, "")
    if value is None:
        return ""
    return str(value).strip()


def _parse_yyyymmdd(value: str) -> date:
    return date(
        int(value[0:4]),
        int(value[4:6]),
        int(value[6:8]),
    )


def _derive_range_end_date(start_date: date, end_mmdd: str) -> date:
    end_month = int(end_mmdd[0:2])
    end_day = int(end_mmdd[2:4])
    end_year = start_date.year
    if (end_month, end_day) < (start_date.month, start_date.day):
        end_year += 1
    return date(end_year, end_month, end_day)
