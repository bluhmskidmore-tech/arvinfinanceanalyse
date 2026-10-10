/**
 * 团队绩效考核底稿 client：GET /api/team-performance/assessment-workbook。
 *
 * 后端为 `backend/app/services/team_performance_service.py` 的静态底稿服务：
 * 2025 部室考核底稿（Excel 静态迁移）+ 后端预汇总，口径为
 * 「静态底稿·非正式口径（后端下发）」（basis=analytical，formal_use_allowed=false）。
 * 前端只消费下发字段，不再持有底稿常量、不再本地加总。
 */
import type { TeamPerformanceAssessmentWorkbookEnvelope } from "./contracts";

export type TeamPerformanceClientMethods = {
  getTeamPerformanceAssessmentWorkbook: () => Promise<TeamPerformanceAssessmentWorkbookEnvelope>;
};

type TeamPerformanceClientFactoryOptions = {
  fetchImpl: typeof fetch;
  baseUrl: string;
};

export const TEAM_PERFORMANCE_ASSESSMENT_WORKBOOK_PATH =
  "/api/team-performance/assessment-workbook";

export function createRealTeamPerformanceClient({
  fetchImpl,
  baseUrl,
}: TeamPerformanceClientFactoryOptions): TeamPerformanceClientMethods {
  return {
    async getTeamPerformanceAssessmentWorkbook() {
      const response = await fetchImpl(`${baseUrl}${TEAM_PERFORMANCE_ASSESSMENT_WORKBOOK_PATH}`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `Team performance API ${response.status}`);
      }
      return response.json() as Promise<TeamPerformanceAssessmentWorkbookEnvelope>;
    },
  };
}
