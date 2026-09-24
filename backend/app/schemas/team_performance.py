"""团队绩效考核底稿（2025 静态工作簿）响应契约。

数据来源是 2025 年金融市场部绩效考核方案 Excel 底稿的静态迁移
（原前端 `ASSESSMENT_CENTERS_2025` / `CENTER_PNL_MAPPINGS_2025` 常量，数值一字不差），
不是正式绩效读模型：`basis=analytical`、`formal_use_allowed=false`。

分数与权重保持底稿原始浮点值下发；汇总（weight_total / workbook_score /
score_rate / total_workbook_score）由后端按底稿行序累加，前端不再本地重算。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

AssessmentMappingEndpoint = Literal["by-business-ytd", "product-category-ytd"]
AssessmentMappingConfidence = Literal["high", "medium", "linked"]


class AssessmentIndicatorItem(BaseModel):
    """底稿单条考核指标（Excel 行原样迁移，分数为底稿已有得分，不重算评分规则）。"""

    center_id: str
    center_name: str
    indicator_category: str
    metric: str
    target: str
    weight: float
    scoring_text: str
    actual: str
    progress: str
    score: float | None
    source_row: int
    block_label: str | None = None


class AssessmentCenterPnlMapping(BaseModel):
    """部室 -> 正式 YTD 损益证据行的映射规则（仅用于页面映射分析并排展示）。"""

    center_id: str
    endpoint: AssessmentMappingEndpoint
    row_id: str
    pnl_field: str | None = None
    scale_field: str | None = None
    confidence: AssessmentMappingConfidence
    note: str | None = None
    additive: bool | None = None


class AssessmentCenterSummary(BaseModel):
    """单个部室的底稿指标与后端预汇总结果。"""

    center_id: str
    center_name: str
    weight_total: float
    workbook_score: float
    has_pending_score: bool
    score_rate: float | None
    indicators: list[AssessmentIndicatorItem]


class AssessmentWorkbookPayload(BaseModel):
    """2025 部室考核工作簿：底稿 + 映射规则 + 后端汇总 + 口径说明。"""

    assessment_year: int
    caliber_label: str
    caliber_note: str
    source_label: str
    centers: list[AssessmentCenterSummary]
    mappings: list[AssessmentCenterPnlMapping]
    total_workbook_score: float
    total_center_count: int
