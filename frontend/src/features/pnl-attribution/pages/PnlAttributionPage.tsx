import { PnlAttributionView } from "../components/PnlAttributionView";

function getReportDateFromCurrentLocation(): string | undefined {
  const params = new URLSearchParams(window.location.search);
  return params.get("report_date")?.trim() || undefined;
}

/**
 * 损益归因工作台：规模/利率、TPL–市场、损益构成、高级归因与 Campisi 四效应。
 *
 * 深色 owner 由外层 ThemedRouteBoundary 的 data-moss-theme="dark" 承担；
 * 页根只声明 Nocturne scope，重复声明 owner 会让深色路由校验判定出两个 owner。
 */
export default function PnlAttributionPage() {
  const reportDate = getReportDateFromCurrentLocation();

  return (
    <div
      data-moss-theme-scope="pnl-attribution"
      className="pnl-attribution-page theme-dh-api"
    >
      <PnlAttributionView reportDate={reportDate} />
    </div>
  );
}
