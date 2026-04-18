from __future__ import annotations

from backend.app.schemas.source_preview import PreviewColumn

ROW_LABELS_BY_FAMILY: dict[str, dict[str, str]] = {
    "zqtz": {
        "ingest_batch_id": "批次ID",
        "row_locator": "行号",
        "report_date": "报告日期",
        "business_type_primary": "业务种类1",
        "business_type_final": "业务种类2归类",
        "asset_group": "资产分组",
        "instrument_code": "债券代码",
        "instrument_name": "债券名称",
        "account_category": "账户类别",
        "manual_review_needed": "需人工复核",
        "source_version": "数据版本",
        "rule_version": "规则版本",
    },
    "tyw": {
        "ingest_batch_id": "批次ID",
        "row_locator": "行号",
        "report_date": "报告日期",
        "business_type_primary": "业务种类1",
        "product_group": "产品分组",
        "institution_category": "机构类型",
        "special_nature": "特殊性质",
        "counterparty_name": "对手方名称",
        "investment_portfolio": "投资组合",
        "manual_review_needed": "需人工复核",
        "source_version": "数据版本",
        "rule_version": "规则版本",
    },
    "pnl": {
        "source_family": "源类型",
        "ingest_batch_id": "批次ID",
        "row_locator": "行号",
        "report_date": "报告日期",
        "instrument_code": "债券代码",
        "invest_type_raw": "投资类型原值",
        "portfolio_name": "投资组合",
        "cost_center": "成本中心",
        "currency": "币种",
        "manual_review_needed": "需人工复核",
        "source_version": "数据版本",
        "rule_version": "规则版本",
    },
    "pnl_514": {
        "source_family": "源类型",
        "ingest_batch_id": "批次ID",
        "row_locator": "行号",
        "report_date": "报告日期",
        "journal_type": "分录类型",
        "product_type": "产品类型",
        "asset_code": "资产代码",
        "account_code": "科目号",
        "dc_flag_raw": "借贷标识",
        "raw_amount": "原始金额",
        "manual_review_needed": "需人工复核",
        "source_version": "数据版本",
        "rule_version": "规则版本",
    },
    "pnl_516": {
        "source_family": "源类型",
        "ingest_batch_id": "批次ID",
        "row_locator": "行号",
        "report_date": "报告日期",
        "journal_type": "分录类型",
        "product_type": "产品类型",
        "asset_code": "资产代码",
        "account_code": "科目号",
        "dc_flag_raw": "借贷标识",
        "raw_amount": "原始金额",
        "manual_review_needed": "需人工复核",
        "source_version": "数据版本",
        "rule_version": "规则版本",
    },
    "pnl_517": {
        "source_family": "源类型",
        "ingest_batch_id": "批次ID",
        "row_locator": "行号",
        "report_date": "报告日期",
        "journal_type": "分录类型",
        "product_type": "产品类型",
        "asset_code": "资产代码",
        "account_code": "科目号",
        "dc_flag_raw": "借贷标识",
        "raw_amount": "原始金额",
        "manual_review_needed": "需人工复核",
        "source_version": "数据版本",
        "rule_version": "规则版本",
    },
}

TRACE_LABELS: dict[str, str] = {
    "ingest_batch_id": "批次ID",
    "row_locator": "行号",
    "trace_step": "轨迹步骤",
    "field_name": "字段名",
    "field_value": "字段值",
    "derived_label": "归类标签",
    "manual_review_needed": "需人工复核",
}


def _build_preview_columns(source_family: str, columns: list[str]) -> list[PreviewColumn]:
    labels = ROW_LABELS_BY_FAMILY.get(source_family, {})
    return [
        PreviewColumn(
            key=column,
            label=labels.get(column, column),
            type=_preview_column_type(column),
        )
        for column in columns
    ]


def _build_trace_columns(columns: list[str]) -> list[PreviewColumn]:
    return [
        PreviewColumn(
            key=column,
            label=TRACE_LABELS.get(column, column),
            type=_preview_column_type(column),
        )
        for column in columns
    ]


def _preview_column_type(column: str) -> str:
    if column in {"row_locator", "trace_step"}:
        return "number"
    if column in {"manual_review_needed"}:
        return "boolean"
    return "string"
