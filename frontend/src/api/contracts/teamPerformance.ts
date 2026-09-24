/**
 * 团队绩效考核底稿契约（`GET /api/team-performance/assessment-workbook`）。
 *
 * 后端 `backend/app/schemas/team_performance.py` 的镜像：2025 部室考核底稿
 * （Excel 静态迁移）+ 后端预汇总（weight_total / workbook_score / score_rate /
 * total_workbook_score）。口径为「静态底稿·非正式口径（后端下发）」，
 * `result_meta.basis=analytical`、`formal_use_allowed=false`；前端只展示、不重算汇总。
 * 分数与权重为底稿浮点原值（非正式金额字段，不走 Decimal string 序列化）。
 */
import type { ApiEnvelope } from "./core";

export type TeamPerformanceMappingEndpoint = "by-business-ytd" | "product-category-ytd";
export type TeamPerformanceMappingConfidence = "high" | "medium" | "linked";
export type TeamPerformanceMappingMetricField =
  | "business_net_income"
  | "cny_net"
  | "cny_scale"
  | "foreign_scale"
  | "foreign_net";

export type TeamPerformanceAssessmentIndicator = {
  center_id: string;
  center_name: string;
  indicator_category: string;
  metric: string;
  target: string;
  weight: number;
  scoring_text: string;
  actual: string;
  progress: string;
  score: number | null;
  source_row: number;
  block_label?: string | null;
};

export type TeamPerformanceCenterPnlMapping = {
  center_id: string;
  endpoint: TeamPerformanceMappingEndpoint;
  row_id: string;
  pnl_field?: TeamPerformanceMappingMetricField | null;
  scale_field?: TeamPerformanceMappingMetricField | null;
  confidence: TeamPerformanceMappingConfidence;
  note?: string | null;
  additive?: boolean | null;
};

export type TeamPerformanceAssessmentCenter = {
  center_id: string;
  center_name: string;
  weight_total: number;
  workbook_score: number;
  has_pending_score: boolean;
  score_rate: number | null;
  indicators: TeamPerformanceAssessmentIndicator[];
};

export type TeamPerformanceAssessmentWorkbookPayload = {
  assessment_year: number;
  caliber_label: string;
  caliber_note: string;
  source_label: string;
  centers: TeamPerformanceAssessmentCenter[];
  mappings: TeamPerformanceCenterPnlMapping[];
  total_workbook_score: number;
  total_center_count: number;
};

export type TeamPerformanceAssessmentWorkbookEnvelope =
  ApiEnvelope<TeamPerformanceAssessmentWorkbookPayload>;
