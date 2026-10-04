import { useLocation } from "react-router-dom";

import { PnlAttributionView } from "../components/PnlAttributionView";

function getReportDateFromCurrentLocation(search: string): string | undefined {
  const params = new URLSearchParams(search);
  return params.get("report_date")?.trim() || undefined;
}

function isIsoDate(value: string | null | undefined): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function getHomeCampisiWindow(search: string, reportDate?: string) {
  const params = new URLSearchParams(search);
  if (params.get("source") !== "dashboard-home") return undefined;
  if (["source", "report_date", "campisi_start_date", "campisi_end_date"].some(
    (key) => params.getAll(key).length !== 1,
  )) return null;
  const startDate = params.get("campisi_start_date");
  const endDate = params.get("campisi_end_date");
  if (!isIsoDate(reportDate) || !isIsoDate(startDate) || !isIsoDate(endDate)) return null;
  if (startDate > endDate || endDate !== reportDate) return null;
  return { startDate, endDate };
}

/**
 * 损益归因工作台：规模/利率、TPL–市场、损益构成、高级归因与 Campisi 四效应。
 *
 * 深色 owner 由外层 ThemedRouteBoundary 的 data-moss-theme="dark" 承担；
 * 页根只声明 Nocturne scope，重复声明 owner 会让深色路由校验判定出两个 owner。
 */
export default function PnlAttributionPage() {
  const location = useLocation();
  const requestedReportDate = getReportDateFromCurrentLocation(location.search);
  const fromHome = new URLSearchParams(location.search).get("source") === "dashboard-home";
  const reportDate = fromHome && !isIsoDate(requestedReportDate)
    ? undefined
    : requestedReportDate;
  const homeCampisiSelection = getHomeCampisiWindow(location.search, reportDate);
  const homeCampisiWindow = homeCampisiSelection ?? undefined;
  const homeCampisiError = homeCampisiSelection === null
    ? "首页 Campisi 链接日期无效或与报告日不一致，请从首页重新打开同区间明细。"
    : undefined;

  return (
    <div
      data-moss-theme-scope="pnl-attribution"
      className="pnl-attribution-page theme-dh-api"
    >
      <PnlAttributionView
        key={location.search}
        reportDate={reportDate}
        homeCampisiWindow={homeCampisiWindow}
        homeCampisiError={homeCampisiError}
      />
    </div>
  );
}
